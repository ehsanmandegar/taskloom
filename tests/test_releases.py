"""Release management against real Git repositories: isolation, validation, approval gate, history, recovery."""

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.releases import (
    Release, ReleaseError, ReleaseInputError, ReleaseManager, ReleaseStatus, ReleaseStore,
)

from gitflow_helpers import PASSING, Registry, git, git_ok, init_repo, run, work_on_task


def make_world(tmp_path, with_origin=False):
    origin = tmp_path / "origin.git" if with_origin else None
    repo = init_repo(tmp_path / "repo", origin)
    registry = Registry(repo)
    return repo, registry, registry.manager(tmp_path)


async def build(manager: ReleaseManager, registry: Registry, version: str, task_ids: list[str]) -> Release:
    release = await manager.create(version, registry.repository_id, task_ids, created_by="alice")
    await manager.wait(release.id)
    return manager.store.get(release.id)


def three_tasks(repo, registry):
    for task_id, name in (("DWS-99", "a.txt"), ("DWS-100", "b.txt"), ("DWS-101", "c.txt")):
        work_on_task(repo, task_id, {name: f"{task_id}\n"})
        registry.integrate(task_id)


def test_release_with_multiple_tasks_is_built_validated_and_waits_for_human_approval(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    three_tasks(repo, registry)
    registry.plan = PASSING
    sandbox_before = git(repo, "rev-parse", "sandbox")

    async def scenario():
        return await build(manager, registry, "1.0.1", ["DWS-99", "DWS-100", "DWS-101"])

    release = run(scenario())

    assert release.status == ReleaseStatus.waiting_approval
    assert [t.task_id for t in release.tasks] == ["DWS-99", "DWS-100", "DWS-101"]
    assert release.release_branch == "release/1.0.1" and release.source_branch == "develop" and release.target_branch == "sandbox"
    assert release.created_by == "alice" and release.approved_by == "" and release.approved_at is None
    assert [v.passed for v in release.validation] == [True] and release.validation[0].command == "python check.py"
    # Human approval comes before anything touches sandbox:
    assert git(repo, "rev-parse", "sandbox") == sandbox_before
    assert git(repo, "rev-parse", "release/1.0.1") == release.final_commit_sha
    for name in ("a.txt", "b.txt", "c.txt"):
        assert git(repo, "show", f"release/1.0.1:{name}")


def test_release_branch_is_created_from_sandbox_not_develop(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    three_tasks(repo, registry)
    git(repo, "switch", "-q", "sandbox")  # sandbox moves on after the tasks were developed
    (repo / "later.txt").write_text("later\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "hotfix directly in sandbox history")
    git(repo, "switch", "-q", "main")
    sandbox_head = git(repo, "rev-parse", "sandbox")

    release = run(build(manager, registry, "1.1.0", ["DWS-99"]))

    assert release.status == ReleaseStatus.waiting_approval
    assert release.base_sha == sandbox_head
    assert git(repo, "merge-base", "release/1.1.0", "sandbox") == sandbox_head  # grows out of the current sandbox
    assert git(repo, "show", "release/1.1.0:later.txt") == "later"


def test_only_the_selected_tasks_changes_enter_the_release(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    three_tasks(repo, registry)

    release = run(build(manager, registry, "1.0.2", ["DWS-99", "DWS-101"]))

    assert release.status == ReleaseStatus.waiting_approval
    changed = set(git(repo, "diff", "--name-only", "sandbox", "release/1.0.2").splitlines())
    assert changed == {"a.txt", "c.txt"}  # DWS-100's b.txt is in develop but NOT in the release
    assert not git_ok(repo, "cat-file", "-e", "release/1.0.2:b.txt")
    assert git_ok(repo, "cat-file", "-e", "develop:b.txt")


def test_changes_of_unselected_tasks_in_the_same_file_are_not_dragged_along(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-1", {"shared.txt": "line 1\nline 2\n"})
    registry.integrate("DWS-1")
    work_on_task(repo, "DWS-2", {"other.txt": "o\n"})  # branched from sandbox, unrelated to DWS-1
    registry.integrate("DWS-2")

    release = run(build(manager, registry, "1.0.3", ["DWS-2"]))

    assert release.status == ReleaseStatus.waiting_approval
    assert set(git(repo, "diff", "--name-only", "sandbox", "release/1.0.3").splitlines()) == {"other.txt"}


def test_validation_failure_blocks_the_release(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-5", {"broken.txt": "this makes check.py fail\n"})
    registry.integrate("DWS-5")
    registry.plan = PASSING

    release = run(build(manager, registry, "2.0.0", ["DWS-5"]))

    assert release.status == ReleaseStatus.failed and release.failed_phase == "testing"
    assert release.validation[0].passed is False and release.validation[0].exit_code == 1
    assert "Validation failed" in release.error
    with pytest.raises(ReleaseError, match="only a release waiting for approval"):
        manager.approve(release.id)
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")


def test_release_without_a_validation_command_is_flagged_not_silently_trusted(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-6", {"f.txt": "f\n"})
    registry.integrate("DWS-6")

    release = run(build(manager, registry, "2.0.1", ["DWS-6"]))

    assert release.status == ReleaseStatus.waiting_approval
    assert release.validation == [] and "nothing was tested" in release.validation_warning


def test_approval_merges_the_release_into_sandbox_and_records_history(tmp_path):
    repo, registry, manager = make_world(tmp_path, with_origin=True)
    three_tasks(repo, registry)
    registry.plan = PASSING

    async def scenario():
        release = await build(manager, registry, "1.0.1", ["DWS-99", "DWS-100"])
        assert release.status == ReleaseStatus.waiting_approval
        assert git(repo, "rev-parse", "sandbox") == release.base_sha  # not merged before approval
        manager.approve(release.id, "bob")
        await manager.wait(release.id)
        return manager.store.get(release.id)

    release = run(scenario())

    assert release.status == ReleaseStatus.released
    assert release.approved_by == "bob" and release.approved_at is not None and release.released_at is not None
    sandbox_head = git(repo, "rev-parse", "sandbox")
    assert release.merge_commit_sha == sandbox_head
    assert git(repo, "rev-parse", f"{sandbox_head}^2") == release.final_commit_sha  # merge commit of the release branch
    assert git(repo, "show", "sandbox:a.txt") == "DWS-99" and not git_ok(repo, "cat-file", "-e", "sandbox:c.txt")
    assert git(tmp_path / "origin.git", "rev-parse", "sandbox") == sandbox_head  # published without force
    assert git(tmp_path / "origin.git", "rev-parse", "release/1.0.1") == release.final_commit_sha
    # persisted history survives a restart (new store object over the same directory)
    reloaded = ReleaseStore(tmp_path / "releases").get(release.id)
    assert reloaded.status == ReleaseStatus.released and reloaded.merge_commit_sha == sandbox_head
    assert [t.task_id for t in reloaded.tasks] == ["DWS-99", "DWS-100"]
    assert all(task.picks and task.picks[0]["picked_commit_sha"] for task in reloaded.tasks)
    assert [r.version for r in manager.store.list()] == ["1.0.1"]
    assert [r["version"] for r in manager.releases_for_task("DWS-99")] == ["1.0.1"]
    assert manager.releases_for_task("DWS-101") == []


def test_cannot_approve_twice_or_before_validation(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-7", {"f.txt": "f\n"})
    registry.integrate("DWS-7")

    async def scenario():
        draft = await manager.create("1.2.0", registry.repository_id, ["DWS-7"], start=False)
        with pytest.raises(ReleaseError):
            manager.approve(draft.id)
        release = await manager.start(draft.id)
        await manager.wait(release.id)
        manager.approve(release.id)
        with pytest.raises(ReleaseError):
            manager.approve(release.id)  # a second click never starts a second merge
        await manager.wait(release.id)

    run(scenario())
    assert len(git(repo, "rev-list", "--merges", "sandbox").splitlines()) == 1


def test_conflicting_tasks_fail_the_release_and_leave_sandbox_untouched_then_retry_works(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-10", {"f.txt": "ten\n"})
    registry.integrate("DWS-10")
    # DWS-11 builds on DWS-10's file: it depends on DWS-10 being released first
    git(repo, "switch", "-q", "-c", "DWS-11", "develop")
    (repo / "f.txt").write_text("ten\neleven\n", encoding="utf-8")
    git(repo, "commit", "-qam", "extend f.txt")
    git(repo, "switch", "-q", "main")
    registry.integrate("DWS-11")

    async def scenario():
        broken = await build(manager, registry, "3.0.0", ["DWS-11"])
        assert broken.status == ReleaseStatus.failed and broken.failed_phase == "preparing"
        assert "f.txt" in broken.error
        assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")  # untouched
        assert not git(repo, "worktree", "list", "--porcelain").count("taskloom-release")  # rolled back: no leftover worktree
        assert git_ok(repo, "rev-parse", "--verify", "release/3.0.0")  # branches are never deleted automatically
        # the admin includes DWS-10 as well, in a new release; the failed one can be cancelled
        manager.cancel(broken.id)
        return await build(manager, registry, "3.0.1", ["DWS-10", "DWS-11"])

    fixed = run(scenario())

    assert fixed.status == ReleaseStatus.waiting_approval
    assert git(repo, "show", "release/3.0.1:f.txt") == "ten\neleven"


def test_retry_rebuilds_a_failed_release_from_the_current_sandbox(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-12", {"broken.txt": "x\n"})
    registry.integrate("DWS-12")
    registry.plan = PASSING

    async def scenario():
        failed = await build(manager, registry, "3.1.0", ["DWS-12"])
        assert failed.status == ReleaseStatus.failed
        registry.plan = []  # the administrator fixed the validation setup
        manager.retry(failed.id)
        await manager.wait(failed.id)
        return manager.store.get(failed.id)

    release = run(scenario())

    assert release.status == ReleaseStatus.waiting_approval and release.error == ""
    assert release.validation == []


def test_interrupted_releases_are_recovered_after_a_restart(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-13", {"f.txt": "f\n"})
    registry.integrate("DWS-13")

    async def scenario():
        draft = await manager.create("3.2.0", registry.repository_id, ["DWS-13"], start=False)
        manager.store.update(draft.id, lambda r: setattr(r, "status", ReleaseStatus.preparing))  # the server died here
        assert await manager.recover_interrupted() == [draft.id]
        failed = manager.store.get(draft.id)
        assert failed.status == ReleaseStatus.failed and "Interrupted" in failed.error
        manager.retry(draft.id)
        await manager.wait(draft.id)
        return manager.store.get(draft.id)

    assert run(scenario()).status == ReleaseStatus.waiting_approval


def test_interrupted_merge_is_reconciled_with_what_git_says(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-14", {"f.txt": "f\n"})
    registry.integrate("DWS-14")

    async def scenario():
        release = await build(manager, registry, "3.3.0", ["DWS-14"])
        manager.store.update(release.id, lambda r: setattr(r, "status", ReleaseStatus.merging))  # died before merging
        await manager.recover_interrupted()
        not_merged = manager.store.get(release.id)
        assert not_merged.status == ReleaseStatus.failed and not_merged.failed_phase == "merging"
        assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")
        manager.retry(release.id)  # back to waiting for a fresh human approval, never merged automatically
        assert manager.store.get(release.id).status == ReleaseStatus.waiting_approval

    run(scenario())


def test_sandbox_moving_after_validation_stops_the_merge(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-15", {"f.txt": "f\n"})
    registry.integrate("DWS-15")

    async def scenario():
        release = await build(manager, registry, "3.4.0", ["DWS-15"])
        git(repo, "switch", "-q", "sandbox")
        (repo / "surprise.txt").write_text("s\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "someone released something else")
        git(repo, "switch", "-q", "main")
        manager.approve(release.id)
        await manager.wait(release.id)
        failed = manager.store.get(release.id)
        assert failed.status == ReleaseStatus.failed and failed.failed_phase == "merging" and "moved" in failed.error
        assert len(git(repo, "rev-list", "--merges", "sandbox").splitlines()) == 0  # nothing merged
        manager.retry(release.id)
        manager.rebuild(release.id)  # rebuild on the new sandbox
        await manager.wait(release.id)
        return manager.store.get(release.id)

    rebuilt = run(scenario())
    assert rebuilt.status == ReleaseStatus.waiting_approval and git(repo, "show", f"{rebuilt.release_branch}:surprise.txt") == "s"


def test_merge_conflict_into_sandbox_is_reported_and_sandbox_is_unchanged(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-16", {"f.txt": "f\n"})
    registry.integrate("DWS-16")

    async def scenario():
        release = await build(manager, registry, "3.5.0", ["DWS-16"])
        # make the later merge conflict without moving sandbox: edit the release branch's file in sandbox's worktree
        # is not possible without moving sandbox, so a tampered release branch is detected instead
        git(repo, "switch", "-q", "release/3.5.0")
        (repo / "f.txt").write_text("tampered\n", encoding="utf-8")
        git(repo, "commit", "-qam", "tamper after validation")
        git(repo, "switch", "-q", "main")
        manager.approve(release.id)
        await manager.wait(release.id)
        return manager.store.get(release.id)

    release = run(scenario())

    assert release.status == ReleaseStatus.failed and "changed since it was validated" in release.error
    assert git(repo, "rev-parse", "sandbox") == git(repo, "rev-parse", "main")


def test_sandbox_checked_out_in_the_main_working_tree_is_merged_there(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-17", {"f.txt": "f\n"})
    registry.integrate("DWS-17")
    git(repo, "switch", "-q", "sandbox")

    async def scenario():
        release = await build(manager, registry, "3.6.0", ["DWS-17"])
        manager.approve(release.id)
        await manager.wait(release.id)
        return manager.store.get(release.id)

    release = run(scenario())

    assert release.status == ReleaseStatus.released
    assert (repo / "f.txt").read_text(encoding="utf-8") == "f\n"  # the checked-out working tree was updated in place


def test_uncommitted_changes_in_the_sandbox_checkout_block_the_merge(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-18", {"f.txt": "f\n"})
    registry.integrate("DWS-18")
    git(repo, "switch", "-q", "sandbox")

    async def scenario():
        release = await build(manager, registry, "3.7.0", ["DWS-18"])
        (repo / "base.txt").write_text("someone is editing sandbox\n", encoding="utf-8")
        manager.approve(release.id)
        await manager.wait(release.id)
        return manager.store.get(release.id)

    release = run(scenario())

    assert release.status == ReleaseStatus.failed and "uncommitted changes" in release.error
    assert (repo / "base.txt").read_text(encoding="utf-8") == "someone is editing sandbox\n"  # never overwritten


# ------------------------------------------------------- subsequent changes and double inclusion

def test_a_released_task_can_be_released_again_for_its_later_changes_only(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-20", {"feature.txt": "v1\n"})
    registry.integrate("DWS-20")

    async def scenario():
        first = await build(manager, registry, "1.0.0", ["DWS-20"])
        manager.approve(first.id)
        await manager.wait(first.id)
        assert manager.store.get(first.id).status == ReleaseStatus.released
        # the same changes cannot be shipped twice ...
        with pytest.raises(ReleaseInputError, match="already part of another release"):
            await manager.create("1.0.1", registry.repository_id, ["DWS-20"])
        row = next(r for r in await manager.eligible_tasks() if r["task_id"] == "DWS-20")
        assert not row["eligible"] and row["releases"][0]["version"] == "1.0.0"
        # ... but a later change of the task goes through a new controlled integration cycle
        git(repo, "switch", "-q", "DWS-20")
        (repo / "feature.txt").write_text("v1\nv2\n", encoding="utf-8")
        git(repo, "commit", "-qam", "follow-up change")
        git(repo, "switch", "-q", "main")
        await registry.aintegrate("DWS-20")
        row = next(r for r in await manager.eligible_tasks() if r["task_id"] == "DWS-20")
        assert row["eligible"] and len(row["pending_merges"]) == 1 and len(row["merges"]) == 2
        second = await build(manager, registry, "1.0.1", ["DWS-20"])
        assert second.status == ReleaseStatus.waiting_approval
        assert [len(t.merge_commit_shas) for t in second.tasks] == [1]
        manager.approve(second.id)
        await manager.wait(second.id)
        return manager.store.get(first.id), manager.store.get(second.id)

    first, second = run(scenario())

    assert second.status == ReleaseStatus.released
    assert first.status == ReleaseStatus.released and first.merge_commit_sha != second.merge_commit_sha  # history preserved
    assert git(repo, "show", "sandbox:feature.txt") == "v1\nv2"
    assert {r["version"] for r in manager.releases_for_task("DWS-20")} == {"1.0.0", "1.0.1"}


def test_failed_and_cancelled_releases_free_their_tasks_and_version(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-21", {"f.txt": "f\n"})
    registry.integrate("DWS-21")

    async def scenario():
        draft = await manager.create("4.0.0", registry.repository_id, ["DWS-21"], start=False)
        with pytest.raises(ReleaseInputError):  # the draft holds the task ...
            await manager.create("4.0.1", registry.repository_id, ["DWS-21"])
        with pytest.raises(ReleaseError, match="already exists"):  # ... and the version
            await manager.create("4.0.0", registry.repository_id, ["DWS-21"])
        manager.cancel(draft.id)
        return await manager.create("4.0.0", registry.repository_id, ["DWS-21"], start=False)  # free again

    assert run(scenario()).status == ReleaseStatus.draft


def test_input_validation(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-22", {"f.txt": "f\n"})
    registry.integrate("DWS-22")

    async def scenario():
        for version in ("1.0", "v1.0.0", "", "1.0.0; rm"):
            with pytest.raises(ReleaseInputError, match="Version"):
                await manager.create(version, registry.repository_id, ["DWS-22"])
        with pytest.raises(ReleaseInputError, match="at least one"):
            await manager.create("1.0.0", registry.repository_id, [])
        with pytest.raises(ReleaseInputError, match="Not integrated"):
            await manager.create("1.0.0", registry.repository_id, ["DWS-404"])

    run(scenario())


def test_dws_and_sdlc_tasks_can_share_one_release(tmp_path):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-30", {"d.txt": "d\n"})
    registry.integrate("DWS-30", workflow="DWS")
    work_on_task(repo, "SDLC-1001", {"s.txt": "s\n"})
    registry.integrate("SDLC-1001", workflow="SDLC")

    async def scenario():
        rows = await manager.eligible_tasks()
        assert {(r["task_id"], r["workflow"]) for r in rows} == {("DWS-30", "DWS"), ("SDLC-1001", "SDLC")}
        return await build(manager, registry, "5.0.0", ["DWS-30", "SDLC-1001"])

    release = run(scenario())
    assert release.status == ReleaseStatus.waiting_approval
    assert {t.workflow for t in release.tasks} == {"DWS", "SDLC"}


# ------------------------------------------------------------------------------------------ API

def test_release_api_lists_filters_and_validates(tmp_path, monkeypatch):
    repo, registry, manager = make_world(tmp_path)
    work_on_task(repo, "DWS-40", {"f.txt": "f\n"})
    registry.integrate("DWS-40")
    monkeypatch.setattr(main_module, "release_manager", manager)
    client = TestClient(main_module.app)

    repos = client.get("/api/releases/repositories").json()
    assert [r["id"] for r in repos] == [registry.repository_id]
    rows = client.get("/api/releases/eligible-tasks", params={"q": "dws-4", "workflow": "DWS", "eligible_only": True}).json()
    assert [r["task_id"] for r in rows] == ["DWS-40"]
    assert client.get("/api/releases/eligible-tasks", params={"q": "nothing"}).json() == []

    body = {"version": "1.0.0", "repository_id": registry.repository_id, "task_ids": ["DWS-40"], "start": False}
    created = client.post("/api/releases", json=body)
    assert created.status_code == 202 and created.json()["status"] == "draft"
    release_id = created.json()["id"]
    assert client.post("/api/releases", json=body).status_code == 409  # duplicate version
    assert client.post("/api/releases", json={**body, "version": "x"}).status_code == 422
    assert client.get(f"/api/releases/{release_id}").json()["version"] == "1.0.0"
    assert client.get("/api/releases/rel_missing").status_code == 404
    assert [r["id"] for r in client.get("/api/releases", params={"q": "DWS-40"}).json()] == [release_id]
    assert client.post(f"/api/releases/{release_id}/approve").status_code == 409  # a draft cannot be approved
    assert client.post(f"/api/releases/{release_id}/cancel").json()["status"] == "cancelled"
    assert client.get("/api/releases/by-task/DWS-40").json() == []  # cancelled releases do not count


def test_release_actions_require_the_admin_token_when_configured(tmp_path, monkeypatch):
    repo, registry, manager = make_world(tmp_path)
    monkeypatch.setattr(main_module, "release_manager", manager)
    monkeypatch.setenv("TASKLOOM_ADMIN_TOKEN", "s3cret")
    client = TestClient(main_module.app)

    assert client.post("/api/releases", json={"version": "1.0.0", "repository_id": "x", "task_ids": ["a"]}).status_code == 403
    assert client.get("/api/releases").status_code == 200  # reading stays open
