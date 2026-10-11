import { describe, it, expect, vi, afterEach } from 'vitest';
import { algorithms, initialProfiles, sampleProgram, validateExperiment } from '@/features/pgara/types';
import { getSampleResult } from '@/features/pgara/sample-data';
import { runExperiment } from '@/services/pgara-api';
const request = {program:sampleProgram,registers:4,profiles:initialProfiles,algorithms:algorithms.map(a=>a.id),robustness:0.6};
afterEach(()=>vi.unstubAllGlobals());
describe('PGARA experiment rules',()=>{
  it('supports the three requested comparison algorithms',()=>{
    expect(algorithms.map(a=>a.name)).toEqual(['Static Greedy','Profile-Weighted Greedy','Multi-Profile Potential Game']);
  });
  it('accepts labeled TAC with a return statement',()=>{
    expect(validateExperiment(request)).toEqual([]);
    expect(validateExperiment({...request,program:'t1 = a + b'}).length).toBeGreaterThan(0);
  });
  it('requires at least one selected algorithm',()=>{
    expect(validateExperiment({...request,algorithms:[]})).toContain('Select at least one allocation algorithm.');
  });
  it('rejects negative execution frequencies',()=>{
    expect(validateExperiment({...request,profiles:[{name:'Invalid',frequencies:[1,-1,0,1]}]}).length).toBeGreaterThan(0);
  });
  it('keeps demonstration fixtures labeled as sample regardless of inputs',()=>{
    const result=getSampleResult({...request,registers:8,robustness:0.2});
    expect(result.source).toBe('sample');
    expect(result.results.map(r=>r.dynamicSpillOps)).toEqual([4200,1800,1200]);
  });
  it('includes only selected algorithms in sample responses',()=>{
    expect(getSampleResult({...request,algorithms:['game']}).results.map(r=>r.algorithm)).toEqual(['game']);
  });
  it('reports backend failures without a sample fallback',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(runExperiment(request,{mode:'backend',baseUrl:'http://localhost:8000'})).rejects.toThrow('Cannot connect');
  });
  it('rejects malformed backend allocation responses',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({results:[]})}));
    await expect(runExperiment(request,{mode:'backend',baseUrl:'http://localhost:8000'})).rejects.toThrow('does not match');
  });
});