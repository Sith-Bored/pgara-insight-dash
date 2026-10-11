import type { ExperimentResult, ExperimentRequest, AlgorithmId } from './types';
const fixtures: Record<AlgorithmId, { ops: number; ms: number; costs: number[]; spills: string[] }> = {
  static: { ops: 4200, ms: 0.42, costs: [4200, 3600, 4800], spills: ['t2', 't5'] },
  weighted: { ops: 1800, ms: 0.68, costs: [1800, 2400, 3400], spills: ['t2'] },
  game: { ops: 1200, ms: 1.24, costs: [1200, 1600, 1900], spills: ['t4'] },
};
// Illustrative fixture only. No parsing, liveness analysis, or allocation is performed.
// The adapter filters selected algorithms; all metrics describe the fixed four-register sample.
export function getSampleResult(request: ExperimentRequest): ExperimentResult {
  return {
    source: 'sample',
    results: request.algorithms.map(algorithm => {
      const f = fixtures[algorithm];
      return { algorithm, dynamicSpillOps: f.ops, executionMs: f.ms, spills: f.spills,
        profileCosts: ['Hot loop', 'Balanced', 'Cold-heavy'].map((profile, i) => ({ profile, spillOps: f.costs[i] ?? 0 })),
        assignments: ['t1','t2','t3','t4','t5','t6'].map((virtual, i) => ({ virtual, physical: f.spills.includes(virtual) ? null : `R${[0,1,2,1,3,0][i]}`, liveRange: ['2–13', '3–13', '4–17', '9–10', '10–17', '17–18'][i] ?? '', weight: [2850, 1150, 3000, 850, 1000, 1000][i] ?? 0 })) };
    }),
    graph: { nodes: [ { id:'t1',x:115,y:65,register:0 }, {id:'t2',x:255,y:50,register:1}, {id:'t3',x:335,y:150,register:2}, {id:'t4',x:255,y:245,register:null}, {id:'t5',x:115,y:230,register:3}, {id:'t6',x:45,y:145,register:0} ], edges: [['t1','t2'],['t1','t3'],['t1','t4'],['t1','t5'],['t2','t3'],['t2','t5'],['t3','t4'],['t3','t5'],['t3','t6'],['t5','t6']] },
    trace: [
      {step:1,action:'Initialize allocation',detail:'Construct interference graph with 6 virtual registers and 10 edges.',potential:4200,status:'Initialization'},
      {step:2,action:'Prioritize hot live ranges',detail:'Assign t3 → R2. Its live range intersects all three execution paths.',potential:2800,status:'Accepted'},
      {step:3,action:'Evaluate unilateral move',detail:'Move t5 → R3; reduce weighted spill cost across the profile set.',potential:1800,status:'Accepted'},
      {step:4,action:'Choose spill candidate',detail:'Spill t4 rather than t2; improve the worst-profile cost.',potential:1200,status:'Accepted'},
      {step:5,action:'Reach stable allocation',detail:'No improving move remains in this illustrative decision sequence.',potential:1200,status:'Converged'},
    ],
  };
}
