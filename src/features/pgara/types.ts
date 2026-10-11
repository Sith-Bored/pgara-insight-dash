export const algorithms = [
  { id: 'static', name: 'Static Greedy', short: 'Static greedy', color: 'static' },
  { id: 'weighted', name: 'Profile-Weighted Greedy', short: 'Profile-weighted', color: 'weighted' },
  { id: 'game', name: 'Multi-Profile Potential Game', short: 'Potential game', color: 'game' },
] as const;
export type AlgorithmId = typeof algorithms[number]['id'];
export interface Profile { name: string; frequencies: number[] }
export interface ExperimentRequest { program: string; registers: number; profiles: Profile[]; algorithms: AlgorithmId[]; robustness: number }
export interface Assignment { virtual: string; physical: string | null; liveRange: string; weight: number }
export interface AlgorithmResult { algorithm: AlgorithmId; assignments: Assignment[]; spills: string[]; dynamicSpillOps: number; executionMs: number; profileCosts: { profile: string; spillOps: number }[] }
export interface GraphNode { id: string; x: number; y: number; register: number | null }
export interface ExperimentResult { source: 'sample' | 'backend'; results: AlgorithmResult[]; graph: { nodes: GraphNode[]; edges: [string, string][] }; trace: { step: number; action: string; detail: string; potential: number; status: string }[] }
export const sampleProgram = `B0:                         # entry\n  t1 = a + b\n  t2 = c * d\n  t3 = t1 + t2\n  if t3 > 10 goto B1\n  goto B2\n\nB1:                         # hot path\n  t4 = t3 * 2\n  t5 = t4 + t1\n  goto B3\n\nB2:                         # cold path\n  t5 = t2 - t1\n  goto B3\n\nB3:                         # exit\n  t6 = t5 + t3\n  return t6`;
export const initialProfiles: Profile[] = [
  { name: 'Hot loop', frequencies: [1000, 850, 150, 1000] },
  { name: 'Balanced', frequencies: [1000, 500, 500, 1000] },
  { name: 'Cold-heavy', frequencies: [1000, 200, 800, 1000] },
];
export function validateExperiment(request: ExperimentRequest): string[] {
  const errors: string[] = [];
  if (!request.program.trim()) errors.push('Enter a three-address-code program before running.');
  else if (!/^\s*[A-Za-z_]\w*:\s*/m.test(request.program) || !/^\s*return\s+\S+/m.test(request.program)) errors.push('The program must include a labeled basic block and a return statement.');
  if (!Number.isInteger(request.registers) || request.registers < 2 || request.registers > 16) errors.push('Available registers must be a whole number between 2 and 16.');
  if (!request.algorithms.length) errors.push('Select at least one allocation algorithm.');
  if (!Number.isFinite(request.robustness) || request.robustness < 0 || request.robustness > 1) errors.push('Robustness must be between 0 and 1.');
  if (!request.profiles.length || request.profiles.some(p => !p.name.trim() || p.frequencies.length !== 4 || p.frequencies.some(f => !Number.isInteger(f) || f < 0))) errors.push('Each profile needs four nonnegative, whole-number block frequencies.');
  return errors;
}
