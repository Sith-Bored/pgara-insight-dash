import { blockLabels, toBackendSource } from '@/services/pgara-backend';

export const algorithms = [
  { id: 'static', name: 'Static Greedy', short: 'Static greedy', color: 'static' },
  { id: 'weighted', name: 'Profile-Weighted Greedy', short: 'Profile-weighted', color: 'weighted' },
  { id: 'game', name: 'Multi-Profile Potential Game', short: 'Potential game', color: 'game' },
] as const;
export type AlgorithmId = typeof algorithms[number]['id'];
export interface Profile { name: string; frequencies: Array<number | undefined> }
export interface ExperimentRequest { program: string; registers: number; profiles: Profile[]; algorithms: AlgorithmId[]; robustness: number }
export interface Assignment { virtual: string; physical: string | null; liveRange: string; weight: number }
export interface AlgorithmResult { algorithm: AlgorithmId; assignments: Assignment[]; spills: string[]; dynamicSpillOps: number; executionMs: number; profileCosts: { profile: string; spillOps: number }[] }
export interface GraphNode { id: string; x: number; y: number; register: number | null }
export interface ExperimentResult { source: 'sample' | 'backend'; results: AlgorithmResult[]; graph: { nodes: GraphNode[]; edges: [string, string][] }; trace: { step: number; action: string; detail: string; potential: number; status: string }[]; traceStatus?: string }
export const sampleProgram = `block B0:
  t1 = a + b
  t2 = c * d
  t3 = t1 + t2
  if t3 goto B1
  goto B2

block B1:
  t4 = t3 * 2
  t5 = t4 + t1
  goto B3

block B2:
  t5 = t2 - t1
  goto B3

block B3:
  t6 = t5 + t3
  return t6
`;
export const initialProfiles: Profile[] = [
  { name: 'Hot loop', frequencies: [1000, 850, 150, 1000] },
  { name: 'Balanced', frequencies: [1000, 500, 500, 1000] },
  { name: 'Cold-heavy', frequencies: [1000, 200, 800, 1000] },
];
export function validateExperiment(request: ExperimentRequest): string[] {
  const errors: string[] = [];
  const labels = request.program.trim() ? blockLabels(request.program) : [];
  if (!request.program.trim()) errors.push('Enter a three-address-code program before running.');
  else if (!labels.length || !/^\s*return\b/m.test(request.program)) errors.push('The program must include a labeled basic block (`block name:`) and a return statement.');
  else {
    try { toBackendSource(request.program); }
    catch (error) { errors.push(error instanceof Error ? error.message : 'The program could not be translated for the backend.'); }
  }
  if (!Number.isInteger(request.registers) || request.registers < 1 || request.registers > 16) errors.push('Available registers must be a whole number from 1 through 16.');
  if (!request.algorithms.length) errors.push('Select at least one allocation algorithm.');
  if (!Number.isFinite(request.robustness) || request.robustness < 0 || request.robustness > 1) errors.push('Robustness must be between 0 and 1.');
  if (!request.profiles.length || request.profiles.some(p => !p.name.trim() || p.frequencies.some(f => f === undefined || !Number.isInteger(f) || f < 0))) errors.push('Each profile needs a name and nonnegative, whole-number block execution counts.');
  else if (labels.length && request.profiles.some(p => p.frequencies.length !== labels.length)) errors.push(`Each profile needs ${labels.length} execution counts, one for every basic block.`);
  return errors;
}
