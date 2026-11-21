// A task branch is named exactly like its task (DWS-1001, SDLC-1500); older versions used `tasks/<id>`.
const TASK_ID_BRANCH=/^[A-Za-z][A-Za-z0-9]*-\d+$/;
const LEGACY_PREFIX='tasks/';

export function gitTaskRows(branchData){
  return (branchData?.branches||[])
    .filter(branch=>typeof branch.name==='string'&&(TASK_ID_BRANCH.test(branch.name)||(branch.name.startsWith(LEGACY_PREFIX)&&branch.name.length>LEGACY_PREFIX.length)))
    .map(branch=>({
      taskId:branch.name.startsWith(LEGACY_PREFIX)?branch.name.slice(LEGACY_PREFIX.length):branch.name,
      branch:branch.name,
      local:!!branch.local,
      remote:!!branch.remote,
      current:branch.name===branchData.current,
    }));
}
