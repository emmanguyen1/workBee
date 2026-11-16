import test from 'node:test';
import assert from 'node:assert/strict';
import {citationParts,resourceURL} from '../hives/careers/static/bee-logic.mjs';

test('inline citations preserve Unicode around source markers',()=>{
  const parts=citationParts('🐝 Read [cite] now.',[{start:7,end:13,url:'https://www.nsf.gov/',title:'NSF'}]);
  assert.equal(parts.map(p=>p.text).join(''),'🐝 Read  [1]  now.');
  assert.equal(parts[1].url,'https://www.nsf.gov/');
});
test('unsafe, overlapping and malformed citation links are rejected',()=>{
  const parts=citationParts('Read this.',[{start:0,end:4,url:'javascript:alert(1)'},{start:0,end:4,url:'https://example.org'},{start:2,end:8,url:'https://example.org'},{start:8,end:50,url:'https://example.org'}]);
  assert.equal(parts.filter(p=>p.url).length,1);
  assert.equal(resourceURL('https://name:secret@example.org'),null);
  assert.equal(resourceURL('data:text/html,<script>'),null);
  assert.equal(citationParts('<img onerror=bad>')[0].text,'<img onerror=bad>');
});
