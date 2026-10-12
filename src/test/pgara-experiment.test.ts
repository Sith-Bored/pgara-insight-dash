import { describe, it, expect, vi, afterEach } from 'vitest';
import { algorithms, initialProfiles, sampleProgram, validateExperiment } from '@/features/pgara/types';
import { getSampleResult } from '@/features/pgara/sample-data';
import { runExperiment } from '@/services/pgara-api';
import { toBackendSource, toUiAlgorithm } from '@/services/pgara-backend';
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
  it('rejects comparison branches and a register count outside 1 through 16',()=>{
    expect(validateExperiment({...request,program:request.program.replace('if t3 goto B1','if t3 > 10 goto B1')})[0]).toMatch(/Comparison branches/);
    expect(validateExperiment({...request,registers:1})).toEqual([]);
    expect(validateExperiment({...request,registers:0}).length).toBeGreaterThan(0);
    expect(validateExperiment({...request,profiles:[{name:'Short',frequencies:[1,2,3]}]})).toContain('Each profile needs 4 execution counts, one for every basic block.');
  });
  it('rewrites a bare block label into backend IR',()=>{
    expect(toBackendSource('entry:\n  a = 1\n  return a\n')).toContain('block entry:');
  });
  it('does not call the backend in sample mode',async()=>{
    const fetchMock=vi.fn();
    vi.stubGlobal('fetch',fetchMock);
    const result=await runExperiment(request,{mode:'sample',baseUrl:'http://127.0.0.1:8741'});
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.source).toBe('sample');
    expect(result.results.map(r=>r.dynamicSpillOps)).toEqual([4200,1800,1200]);
  });
  it('posts API 1.0 allocate fields and maps the returned assignment',async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>allocateFixture});
    vi.stubGlobal('fetch',fetchMock);
    const result=await runExperiment({...request,algorithms:['static']},{mode:'backend',baseUrl:'http://127.0.0.1:8741/'});
    const call=fetchMock.mock.calls[0] as [string, { body: string }] | undefined;
    if (!call) throw new Error('allocate was not requested');
    const [url, init]=call;
    const body=JSON.parse(init.body) as { profiles: Array<{ block_counts: Record<string, number> }>; source: string };
    expect(url).toBe('http://127.0.0.1:8741/api/allocate');
    expect(body).toMatchObject({num_registers:4,algorithm:'static_greedy',tradeoff:0.6,game_initial:'all_spilled',iteration_budget:200});
    expect(body.profiles[0]?.block_counts).toMatchObject({B0:1000,B1:850,B2:150,B3:1000});
    expect(body.source).toContain('block B0:');
    expect(result.source).toBe('backend');
    expect(result.results).toHaveLength(1);
    const row=result.results[0];
    if (!row) throw new Error('missing allocation result');
    expect(row.assignments.find(item=>item.virtual==='t1')).toMatchObject({physical:'p0',liveRange:'B0:0–B3:1',weight:7});
    expect(row.spills).toEqual(['t2']);
    expect(row.dynamicSpillOps).toBe(9);
    expect(result.graph.edges).toEqual([['t1','t2']]);
    expect(result.trace).toEqual([]);
  });
  it('normalizes API algorithm ids onto the dashboard ids',()=>{
    expect(toUiAlgorithm('potential_game')).toBe('game');
    expect(toUiAlgorithm('profile_greedy')).toBe('weighted');
    expect(toUiAlgorithm('static_greedy')).toBe('static');
    expect(toUiAlgorithm('game')).toBe('game');
    expect(toUiAlgorithm('unknown')).toBeNull();
  });
  it('keeps each algorithm result and the potential-game trace distinct',async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>distinctFixture});
    vi.stubGlobal('fetch',fetchMock);
    const result=await runExperiment(request,{mode:'backend',baseUrl:'http://127.0.0.1:8741'});
    const body=JSON.parse((fetchMock.mock.calls[0] as [string,{body:string}])[1].body) as {algorithm:string};
    expect(body.algorithm).toBe('all');
    expect(result.source).toBe('backend');
    expect(result.results.map(row=>row.algorithm)).toEqual(['static','weighted','game']);
    expect(result.results.map(row=>row.assignments.find(item=>item.virtual==='a')?.physical)).toEqual(['p0','p0',null]);
    expect(result.results.map(row=>row.spills)).toEqual([['b'],['b'],['a']]);
    expect(result.results.map(row=>row.dynamicSpillOps)).toEqual([19,19,20]);
    expect(result.results.map(row=>row.executionMs)).toEqual([0.11,0.08,0.2]);
    expect(result.trace.map(step=>step.action)).toContain('Move b from spill to p0');
    expect(result.traceStatus).toBe('no_improving_move');
  });
});

function liveRange(id: string) {
  return {
    id, vreg: id, static_spill_operations: 2,
    per_profile_estimated_spill_operations: [
      { profile: 'Hot loop', estimated_spill_operations: 4 },
      { profile: 'Balanced', estimated_spill_operations: 2 },
      { profile: 'Cold-heavy', estimated_spill_operations: 1 },
    ],
    defs: [{ block: 'B0', index: 0, kind: 'store' }],
    uses: [{ block: 'B3', index: 1, kind: 'load' }],
  };
}
function algorithmOut(algorithm: string, assignments: Record<string, string | null>, spills: string[], spillOps: number, ms: number, trace: unknown[] = []) {
  return {
    algorithm, status: 'ok', assignments, spills,
    per_profile_costs: [{ profile: 'skew', estimated_spill_operations: spillOps }],
    static_spill_operations: spillOps, execution_time_ms: ms, iterations: trace.length,
    stopping_reason: algorithm === 'potential_game' ? 'no_improving_move' : 'single_pass',
    potential_numerator: spillOps, potential_denominator: 1, potential_float: spillOps,
    decision_trace: trace, valid: true,
  };
}
const distinctFixture = {
  api_version: '1.0',
  blocks: [{ label: 'def_a' }, { label: 'exit' }],
  interference: { nodes: ['a', 'b'], edges: [{ a: 'a', b: 'b' }] },
  live_ranges: ['a', 'b'].map(id => ({ ...liveRange(id), defs: [{ block: 'def_a', index: 0, kind: 'store' }], uses: [{ block: 'exit', index: 0, kind: 'load' }] })),
  results: [
    algorithmOut('static_greedy', { a: 'p0', b: null }, ['b'], 19, 0.11),
    algorithmOut('profile_greedy', { a: 'p0', b: null }, ['b'], 19, 0.08),
    algorithmOut('potential_game', { a: null, b: 'p0' }, ['a'], 20, 0.2, [{
      step: 0, live_range: 'b', action: 'move', previous_strategy: 'spill', strategy: 'p0',
      new_potential_numerator: 10, new_potential_denominator: 1, reason: 'accepted a strictly lower potential',
    }]),
  ],
};
const allocateFixture = {
  api_version: '1.0',
  blocks: [{ label: 'B0' }, { label: 'B1' }, { label: 'B2' }, { label: 'B3' }],
  interference: { nodes: ['t1', 't2'], edges: [{ a: 't1', b: 't2' }] },
  live_ranges: [liveRange('t1'), liveRange('t2')],
  results: [{
    algorithm: 'static_greedy', status: 'ok', assignments: { t1: 'p0', t2: null }, spills: ['t2'],
    per_profile_costs: [{ profile: 'Hot loop', estimated_spill_operations: 9 }],
    static_spill_operations: 3, execution_time_ms: 0.4, iterations: 1, stopping_reason: 'single_pass',
    decision_trace: [], valid: true,
  }],
};