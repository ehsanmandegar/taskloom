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

test('lists branches named exactly like their task id, and ignores the fixed integration branches',()=>{
  const rows=gitTaskRows({current:'DWS-1001',branches:[
    {name:'sandbox',local:true,remote:true},
    {name:'develop',local:true,remote:true},
    {name:'release/1.0.1',local:true,remote:false},
    {name:'DWS-1001',local:true,remote:true},
    {name:'SDLC-1500',local:false,remote:true},
  ]});
  assert.deepEqual(rows,[
    {taskId:'DWS-1001',branch:'DWS-1001',local:true,remote:true,current:true},
    {taskId:'SDLC-1500',branch:'SDLC-1500',local:false,remote:true,current:false},
  ]);
});
