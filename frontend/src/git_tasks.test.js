import assert from 'node:assert/strict';
import test from 'node:test';
import {gitTaskRows} from './git_tasks.js';

test('builds Git task rows from local and origin task branches',()=>{
  const rows=gitTaskRows({current:'tasks/issue-12',branches:[
    {name:'main',local:true,remote:true},
    {name:'tasks/issue-12',local:true,remote:true},
    {name:'tasks/issue-13',local:false,remote:true},
    {name:'tasks/',local:true,remote:false},
  ]});
  assert.deepEqual(rows,[
    {taskId:'issue-12',branch:'tasks/issue-12',local:true,remote:true,current:true},
    {taskId:'issue-13',branch:'tasks/issue-13',local:false,remote:true,current:false},
  ]);
});
