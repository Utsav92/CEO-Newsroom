import test from 'node:test';
import assert from 'node:assert/strict';
import {narrationChunks} from '../src/narration.ts';

test('long researched answers keep every section in bounded narration tracks',()=>{
 const text=('Evidence and context. '+ 'A detailed explanation with qualifications. '.repeat(100)+'\n\n').repeat(3);
 const chunks=narrationChunks(text);
 assert.ok(chunks.length>1);assert.ok(chunks.every(c=>c.length<=3500));assert.equal(chunks.join(''),text);
});
test('short answers need one narration track and empty input needs none',()=>{
 assert.deepEqual(narrationChunks('A short answer.'),['A short answer.']);assert.deepEqual(narrationChunks(''),[]);
});
