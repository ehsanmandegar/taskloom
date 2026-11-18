export function gitTaskRows(branchData){
  return (branchData?.branches||[])
    .filter(branch=>typeof branch.name==='string'&&branch.name.startsWith('tasks/')&&branch.name.length>'tasks/'.length)
    .map(branch=>({
      taskId:branch.name.slice('tasks/'.length),
      branch:branch.name,
      local:!!branch.local,
      remote:!!branch.remote,
      current:branch.name===branchData.current,
    }));
}
