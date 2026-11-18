import asyncio
import hashlib
import sys

import pytest

from backend.app import services
from backend.app.models import AgentType, RunStatus, TaskState


def test_command_receives_large_utf8_stdin_without_shell_expansion(tmp_path):
    prompt = 'سلام "quoted" %PATH% & | $HOME `literal`\n' * 10_000
    script = "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"

    code, output = asyncio.run(services.command(
        [sys.executable, "-c", script], tmp_path, stdin_text=prompt,
    ))

    assert code == 0
    assert output.strip() == hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("resumed", [False, True])
def test_codex_large_prompts_use_stdin_and_preserve_streamed_events(monkeypatch, tmp_path, resumed):
    prompt = "سلام\n" * 20_000
    state = TaskState(
        id="stdin", task_id="stdin", project_path=str(tmp_path),
        branch="tasks/stdin", status=RunStatus.running, step="Running",
    )
    args = (
        services.resume_agent_args(AgentType.codex, sys.executable, "thread-stdin", prompt)
        if resumed else services.initial_agent_args(AgentType.codex, sys.executable, prompt)
    )
    original_args = args.copy()
    real_command = services.command

    async def launch_fake_codex(cli_args, cwd, timeout=900, env=None, stdin_text=None):
        assert cli_args == [*original_args[:-1], "-"]
        assert prompt not in cli_args
        assert stdin_text == prompt
        # Exercise the real process runner and its stream handler with a CLI
        # stand-in, without starting a paid agent or changing repository files.
        script = (
            "import sys,json; text=sys.stdin.buffer.read().decode('utf-8'); "
            "print(json.dumps({'type':'thread.started','thread_id':'thread-stdin'})); "
            "print(json.dumps({'type':'item.completed','item':"
            "{'type':'agent_message','text':str(len(text))}}))"
        )
        return await real_command([sys.executable, "-c", script], cwd, timeout, stdin_text=stdin_text)

    monkeypatch.setattr(services, "command", launch_fake_codex)
    code, output = asyncio.run(services.codex_command(args, tmp_path, state, 10))

    assert code == 0
    assert args == original_args
    assert state.codex_thread_id == "thread-stdin"
    assert state.live_response == str(len(prompt))
    assert services.codex_response(output) == ("thread-stdin", str(len(prompt)))


def test_command_timeout_does_not_wait_for_stdin_consumption(tmp_path):
    code, output = asyncio.run(services.command(
        [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path,
        timeout=1, stdin_text="x" * 1_000_000,
    ))

    assert code == 124
    assert "timed out" in output
