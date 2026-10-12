import { z } from 'zod';
import type { AlgorithmId, AlgorithmResult, ExperimentRequest, ExperimentResult, Profile } from '@/features/pgara/types';

/** Local default. Override with VITE_PGARA_API_URL. */
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8741';

const uiAlgorithm = {
  static_greedy: 'static',
  profile_greedy: 'weighted',
  potential_game: 'game',
} as const;

const apiAlgorithm = {
  static: 'static_greedy',
  weighted: 'profile_greedy',
  game: 'potential_game',
} as const satisfies Record<AlgorithmId, string>;

const profileCostSchema = z.object({
  profile: z.string(),
  estimated_spill_operations: z.number(),
});

const decisionSchema = z.object({
  step: z.number(),
  live_range: z.string(),
  action: z.enum(['assign', 'spill', 'move']),
  previous_strategy: z.string().nullable().optional(),
  strategy: z.string(),
  new_potential_numerator: z.number().nullable().optional(),
  new_potential_denominator: z.number().nullable().optional(),
  potential_float: z.number().nullable().optional(),
  reason: z.string(),
});

const algorithmOutSchema = z.object({
  algorithm: z.enum(['static_greedy', 'profile_greedy', 'potential_game']),
  status: z.enum(['ok', 'skipped']),
  skip_reason: z.string().nullable().optional(),
  assignments: z.record(z.string().nullable()),
  spills: z.array(z.string()),
  per_profile_costs: z.array(profileCostSchema),
  static_spill_operations: z.number().nullable().optional(),
  potential_numerator: z.number().nullable().optional(),
  potential_denominator: z.number().nullable().optional(),
  potential_float: z.number().nullable().optional(),
  execution_time_ms: z.number(),
  iterations: z.number(),
  stopping_reason: z.string().nullable().optional(),
  decision_trace: z.array(decisionSchema),
  valid: z.boolean().nullable().optional(),
});

const siteSchema = z.object({ block: z.string(), index: z.number(), kind: z.string() });

export const allocateResponseSchema = z.object({
  api_version: z.literal('1.0'),
  blocks: z.array(z.object({ label: z.string() })),
  interference: z.object({
    nodes: z.array(z.string()),
    edges: z.array(z.object({ a: z.string(), b: z.string() })),
  }),
  live_ranges: z.array(z.object({
    id: z.string(),
    vreg: z.string(),
    static_spill_operations: z.number(),
    per_profile_estimated_spill_operations: z.array(profileCostSchema),
    defs: z.array(siteSchema),
    uses: z.array(siteSchema),
  })),
  results: z.array(algorithmOutSchema),
});

export const healthResponseSchema = z.object({
  status: z.literal('ok'),
  service: z.literal('pgara'),
  api_version: z.literal('1.0'),
  version: z.string(),
});

export const sampleResponseSchema = z.object({
  api_version: z.literal('1.0'),
  source: z.string(),
  num_registers: z.number().int(),
  profiles: z.array(z.object({
    name: z.string(),
    block_counts: z.record(z.number()),
  })),
  name: z.string(),
  suggested_runs: z.array(z.object({
    tradeoff: z.number(),
    note: z.string().optional(),
  })).optional(),
});

const benchmarkCaseSchema = z.object({
  name: z.string(),
  description: z.string(),
  num_registers: z.number(),
  tradeoff: z.string(),
  results: z.array(algorithmOutSchema),
});

export const benchmarkResponseSchema = z.object({
  api_version: z.literal('1.0'),
  note: z.string(),
  cases: z.array(benchmarkCaseSchema),
});

export type AllocateResponse = z.infer<typeof allocateResponseSchema>;
export type BenchmarkResponse = z.infer<typeof benchmarkResponseSchema>;

export interface LoadedSample {
  name: string;
  source: string;
  numRegisters: number;
  profiles: Profile[];
  tradeoff: number;
  note: string;
}

export interface BenchmarkCaseRow {
  algorithm: string;
  spills: string[];
  spillOps: number;
  executionMs: number;
}

export interface BenchmarkSuite {
  note: string;
  cases: {
    name: string;
    description: string;
    numRegisters: number;
    tradeoff: string;
    rows: BenchmarkCaseRow[];
  }[];
}

export interface HealthStatus {
  state: 'checking' | 'ok' | 'error';
  version?: string;
  apiVersion?: string;
  message?: string;
}

export function blockLabels(program: string): string[] {
  const labels: string[] = [];
  for (const raw of program.split(/\r?\n/)) {
    const trimmed = raw.replace(/#.*$/, '').trim();
    const header = captureLabel(trimmed.match(/^block\s+([A-Za-z_]\w*)\s*:$/));
    if (header) {
      labels.push(header);
      continue;
    }
    const bare = captureLabel(trimmed.match(/^([A-Za-z_]\w*)\s*:$/));
    if (bare) labels.push(bare);
  }
  return labels;
}

/** Rewrite the editor text into the backend IR. Comparisons are rejected, not approximated. */
export function toBackendSource(program: string): string {
  const out: string[] = [];
  for (const raw of program.split(/\r?\n/)) {
    const trimmed = raw.replace(/#.*$/, '').trim();
    if (!trimmed) {
      out.push('');
      continue;
    }
    const header = captureLabel(trimmed.match(/^block\s+([A-Za-z_]\w*)\s*:$/));
    if (header) {
      out.push(`block ${header}:`);
      continue;
    }
    const bare = captureLabel(trimmed.match(/^([A-Za-z_]\w*)\s*:$/));
    if (bare) {
      out.push(`block ${bare}:`);
      continue;
    }
    const comparison = trimmed.match(/^if\s+\S+\s*(?:<=|>=|==|!=|<|>)\s*\S+\s+goto\s+\S+$/);
    if (comparison) {
      throw new Error(`Comparison branches are not part of the backend IR ("${trimmed}"). Use "if <register> goto <label>".`);
    }
    out.push(trimmed);
  }
  return `${out.join('\n').replace(/\n+$/, '')}\n`;
}

function captureLabel(match: RegExpMatchArray | null): string | null {
  const label = match?.[1];
  return label ?? null;
}

export function profilesForBlocks(labels: string[], profiles: Profile[]) {
  return profiles.map(profile => {
    if (profile.frequencies.length !== labels.length) {
      throw new Error(`Profile "${profile.name}" has ${profile.frequencies.length} counts and the program has ${labels.length} blocks.`);
    }
    const block_counts: Record<string, number> = {};
    labels.forEach((label, index) => {
      const count = profile.frequencies[index];
      if (typeof count !== 'number' || !Number.isInteger(count) || count < 0) {
        throw new Error(`Profile "${profile.name}" is missing a nonnegative whole-number count for block ${label}.`);
      }
      block_counts[label] = count;
    });
    return {
      name: profile.name.trim(),
      block_counts,
    };
  });
}

export function allocateBody(request: ExperimentRequest, algorithm: AlgorithmId | 'all') {
  const labels = blockLabels(request.program);
  return {
    source: toBackendSource(request.program),
    num_registers: request.registers,
    profiles: profilesForBlocks(labels, request.profiles),
    algorithm: algorithm === 'all' ? 'all' : apiAlgorithm[algorithm],
    tradeoff: request.robustness,
    iteration_budget: 200,
    game_initial: 'all_spilled' as const,
  };
}

export function mapAllocateResponse(data: AllocateResponse, requested: AlgorithmId[]): ExperimentResult {
  const order = data.interference.nodes.length
    ? data.interference.nodes
    : Object.keys(data.results[0]?.assignments ?? {});
  const ranges = new Map(data.live_ranges.map(range => [range.id, range]));
  const blockOrder = data.blocks.map(block => block.label);
  const results = data.results
    .filter(result => requested.includes(uiAlgorithm[result.algorithm]))
    .map(result => mapAlgorithm(result, ranges, order, blockOrder));
  const game = data.results.find(result => result.algorithm === 'potential_game' && result.status === 'ok');
  const traceStatus = game?.stopping_reason ?? (requested.includes('game') ? 'unavailable' : undefined);
  return {
    source: 'backend',
    results,
    graph: {
      nodes: layoutNodes(order),
      edges: data.interference.edges.map(edge => [edge.a, edge.b] as [string, string]),
    },
    trace: game ? mapTrace(game) : [],
    ...(traceStatus ? { traceStatus } : {}),
  };
}

export function mapBenchmarkResponse(data: BenchmarkResponse): BenchmarkSuite {
  return {
    note: data.note,
    cases: data.cases.map(item => ({
      name: item.name,
      description: item.description,
      numRegisters: item.num_registers,
      tradeoff: item.tradeoff,
      rows: item.results.filter(result => result.status === 'ok').map(result => ({
        algorithm: result.algorithm,
        spills: result.spills,
        spillOps: spillTotal(result),
        executionMs: result.execution_time_ms,
      })),
    })),
  };
}

export function mapSampleProgram(data: z.infer<typeof sampleResponseSchema>): LoadedSample {
  const labels = blockLabels(data.source);
  const missing = data.profiles.flatMap(profile => labels.filter(label => profile.block_counts[label] === undefined));
  if (missing.length) {
    throw new Error(`Sample program is missing execution counts for: ${[...new Set(missing)].join(', ')}`);
  }
  const suggestion = data.suggested_runs?.[0];
  return {
    name: data.name,
    source: data.source.trimEnd() + '\n',
    numRegisters: data.num_registers,
    tradeoff: suggestion?.tradeoff ?? 0.5,
    note: suggestion?.note ?? 'Loaded from GET /api/sample-program. Run the experiment to allocate.',
    profiles: data.profiles.map(profile => ({
      name: profile.name,
      frequencies: labels.map(label => profile.block_counts[label]),
    })),
  };
}

export function apiUrl(baseUrl: string, path: string): string {
  let url: URL;
  try {
    url = new URL(baseUrl);
  } catch {
    throw new Error('Enter a valid HTTP or HTTPS backend URL in connection settings.');
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('Enter a valid HTTP or HTTPS backend URL in connection settings.');
  }
  return `${url.href.replace(/\/$/, '')}${path}`;
}

export async function readBackendError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
    if (body.detail && typeof body.detail === 'object' && 'message' in body.detail) {
      const message = (body.detail as { message?: unknown }).message;
      if (typeof message === 'string') return message;
    }
    if (Array.isArray(body.detail)) {
      const messages = body.detail.map(item => {
        if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') return item.msg;
        return null;
      }).filter((item): item is string => Boolean(item));
      if (messages.length) return messages.join('; ');
    }
  } catch {
    /* The body was not JSON. */
  }
  return `Backend returned HTTP ${response.status}. Check the service and try again.`;
}

function mapAlgorithm(
  result: z.infer<typeof algorithmOutSchema>,
  ranges: Map<string, AllocateResponse['live_ranges'][number]>,
  order: string[],
  blockOrder: string[],
): AlgorithmResult {
  if (result.status === 'skipped') {
    throw new Error(result.skip_reason || `${result.algorithm} was skipped.`);
  }
  if (result.valid === false) {
    throw new Error(`${result.algorithm} returned an invalid allocation.`);
  }
  const spills = new Set(result.spills);
  const assignments = order.filter(id => id in result.assignments).map(id => {
    const range = ranges.get(id);
    const weight = range
      ? (range.per_profile_estimated_spill_operations.length
        ? range.per_profile_estimated_spill_operations.reduce((sum, cost) => sum + cost.estimated_spill_operations, 0)
        : range.static_spill_operations)
      : 0;
    return {
      virtual: id,
      physical: result.assignments[id] ?? null,
      liveRange: range ? formatSpan(range, blockOrder) : id,
      weight,
    };
  });
  for (const id of Object.keys(result.assignments)) {
    if (!assignments.some(item => item.virtual === id)) {
      assignments.push({ virtual: id, physical: result.assignments[id] ?? null, liveRange: id, weight: 0 });
    }
  }
  return {
    algorithm: uiAlgorithm[result.algorithm],
    assignments,
    spills: [...spills],
    dynamicSpillOps: spillTotal(result),
    executionMs: result.execution_time_ms,
    profileCosts: result.per_profile_costs.map(cost => ({ profile: cost.profile, spillOps: cost.estimated_spill_operations })),
  };
}

function spillTotal(result: z.infer<typeof algorithmOutSchema>): number {
  if (result.per_profile_costs.length) {
    return result.per_profile_costs.reduce((sum, cost) => sum + cost.estimated_spill_operations, 0);
  }
  return result.static_spill_operations ?? 0;
}

function formatSpan(range: AllocateResponse['live_ranges'][number], blockOrder: string[]): string {
  const rank = new Map(blockOrder.map((label, index) => [label, index]));
  const sites = [...range.defs, ...range.uses].sort((left, right) => {
    const blockDelta = (rank.get(left.block) ?? blockOrder.length) - (rank.get(right.block) ?? blockOrder.length);
    return blockDelta || left.index - right.index;
  });
  const first = sites[0];
  const last = sites[sites.length - 1];
  if (!first || !last) return range.id;
  if (first.block === last.block && first.index === last.index) return `${first.block}:${first.index}`;
  return `${first.block}:${first.index}–${last.block}:${last.index}`;
}

function mapTrace(result: z.infer<typeof algorithmOutSchema>): ExperimentResult['trace'] {
  const moves = result.decision_trace.map(step => ({
    step: step.step + 1,
    action: step.action === 'move'
      ? `Move ${step.live_range} from ${step.previous_strategy ?? 'spill'} to ${step.strategy}`
      : `${step.action} ${step.live_range}`,
    detail: step.reason,
    potential: rational(step.new_potential_numerator, step.new_potential_denominator, null),
    status: 'Accepted',
  }));
  return [...moves, {
    step: moves.length + 1,
    action: 'Search stopped',
    detail: stopDetail(result),
    potential: rational(result.potential_numerator, result.potential_denominator, result.potential_float),
    status: result.stopping_reason ?? 'stopped',
  }];
}

function stopDetail(result: z.infer<typeof algorithmOutSchema>): string {
  if (result.stopping_reason === 'no_improving_move') {
    return 'No unilateral move strictly lowered the potential. This is a local equilibrium, not a proof of global optimality.';
  }
  if (result.stopping_reason === 'iteration_budget') {
    return `The iteration budget stopped the search after ${result.iterations} accepted moves. This is not a proof of global optimality.`;
  }
  if (result.stopping_reason === 'single_pass') {
    return 'The allocator finished its single pass and did not search further moves.';
  }
  return `Stopping reason: ${result.stopping_reason ?? 'unavailable'}. Iterations: ${result.iterations}.`;
}

function rational(numerator?: number | null, denominator?: number | null, fallback?: number | null): number {
  if (typeof numerator === 'number' && typeof denominator === 'number' && denominator !== 0) return numerator / denominator;
  return fallback ?? 0;
}

function layoutNodes(ids: string[]): ExperimentResult['graph']['nodes'] {
  const cx = 195;
  const cy = 145;
  const rx = ids.length <= 1 ? 0 : 130;
  const ry = ids.length <= 1 ? 0 : 95;
  return ids.map((id, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(ids.length, 1);
    return {
      id,
      x: Math.round(cx + rx * Math.cos(angle)),
      y: Math.round(cy + ry * Math.sin(angle)),
      register: null,
    };
  });
}
