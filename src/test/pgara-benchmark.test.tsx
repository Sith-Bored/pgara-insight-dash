import { useEffect } from 'react';

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExperimentProvider, useExperiment } from '@/features/pgara/experiment-context';
import { ResearchPage } from '@/features/pgara/workspace';
import { runBenchmark } from '@/services/pgara-api';

afterEach(() => vi.unstubAllGlobals());

function BackendBenchmarks() {
  const { setSettings } = useExperiment();
  useEffect(() => {
    setSettings({ mode: 'backend', baseUrl: 'http://127.0.0.1:8741' });
  }, [setSettings]);
  return <ResearchPage view="benchmarks" />;
}

function algorithm(algorithm: string, spills: string[], spillOps: number) {
  return {
    algorithm,
    status: 'ok',
    assignments: {},
    spills,
    per_profile_costs: [{ profile: 'case', estimated_spill_operations: spillOps }],
    static_spill_operations: spillOps,
    execution_time_ms: 0.2,
    iterations: 1,
    stopping_reason: algorithm === 'potential_game' ? 'no_improving_move' : 'single_pass',
    decision_trace: [],
    valid: true,
  };
}

const benchmarkFixture = {
  api_version: '1.0',
  note: 'Estimated spill operations from the built-in programs. Not measured runtime.',
  cases: [
    {
      name: 'profile_versus_static',
      description: 'One physical register. Static spill counts prefer a; the hot-block counts prefer b.',
      num_registers: 1,
      tradeoff: '0',
      results: [
        algorithm('static_greedy', ['b'], 101),
        algorithm('profile_greedy', ['a'], 8),
        algorithm('potential_game', ['a'], 8),
      ],
    },
    {
      name: 'game_average',
      description: 'Two profiles and tradeoff 0. The game keeps a.',
      num_registers: 1,
      tradeoff: '0',
      results: [
        algorithm('static_greedy', ['b'], 19),
        algorithm('profile_greedy', ['b'], 19),
        algorithm('potential_game', ['b'], 19),
      ],
    },
    {
      name: 'game_worst',
      description: 'Same program as game_average with tradeoff 1. The game keeps b.',
      num_registers: 1,
      tradeoff: '1',
      results: [
        algorithm('static_greedy', ['b'], 19),
        algorithm('profile_greedy', ['b'], 19),
        algorithm('potential_game', ['a'], 20),
      ],
    },
  ],
};

const allocateFixture = {
  api_version: '1.0',
  blocks: [{ label: 'B0' }, { label: 'B2' }, { label: 'B1' }, { label: 'B3' }],
  interference: { nodes: ['t1'], edges: [] },
  live_ranges: [{
    id: 't1',
    vreg: 't1',
    static_spill_operations: 1,
    per_profile_estimated_spill_operations: [{ profile: 'Hot loop', estimated_spill_operations: 0 }],
    defs: [{ block: 'B0', index: 0, kind: 'store' }],
    uses: [{ block: 'B3', index: 0, kind: 'load' }],
  }],
  results: ['static_greedy', 'profile_greedy', 'potential_game'].map(name => algorithm(name, [], 0)),
};

function cells(caseName: string, algorithmName: string): string[] {
  const row = screen.getAllByText(caseName)
    .map(node => node.closest('tr'))
    .find(candidate => candidate?.querySelector('td:nth-child(2)')?.textContent === algorithmName);
  if (!row) throw new Error(`missing ${caseName} / ${algorithmName}`);
  return [...row.querySelectorAll('td')].map(cell => cell.textContent ?? '');
}

describe('synthetic benchmark tradeoffs', () => {
  it('posts an empty benchmark body with no tradeoff field', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ api_version: '1.0', note: 'Estimated.', cases: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);
    await runBenchmark('http://127.0.0.1:8741/');
    const call = fetchMock.mock.calls[0] as [string, { body: string }] | undefined;
    if (!call) throw new Error('benchmark was not requested');
    expect(call[0]).toBe('http://127.0.0.1:8741/api/benchmark');
    expect(call[1].body).toBe('{}');
    expect(JSON.parse(call[1].body)).toEqual({});
    expect(Object.hasOwn(JSON.parse(call[1].body) as object, 'tradeoff')).toBe(false);
  });

  it('shows each case tradeoff, spill, and cost from the empty-body suite', async () => {
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (String(url).endsWith('/api/benchmark') ? benchmarkFixture : allocateFixture),
    }));
    vi.stubGlobal('fetch', fetchMock);
    render(<ExperimentProvider><BackendBenchmarks /></ExperimentProvider>);
    expect(await screen.findByText(/Run an experiment to execute the synthetic suite/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Run Allocation Experiment' }));

    expect(await screen.findByText('Each case uses the tradeoff shown in this table. The robustness slider applies only to the program allocation.')).toBeInTheDocument();
    expect(screen.getAllByText(/Two profiles and tradeoff 0/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/tradeoff 1/).length).toBeGreaterThan(0);
    expect(cells('game_average', 'Potential Game').slice(3, 6)).toEqual(['0', 'b', '19']);
    expect(cells('game_worst', 'Potential Game').slice(3, 6)).toEqual(['1', 'a', '20']);
    expect(cells('profile_versus_static', 'Static Greedy').slice(3, 6)).toEqual(['0', 'b', '101']);
    expect(cells('profile_versus_static', 'Profile-Weighted Greedy').slice(3, 6)).toEqual(['0', 'a', '8']);
    expect(cells('profile_versus_static', 'Potential Game').slice(3, 6)).toEqual(['0', 'a', '8']);

    const benchmarkCall = fetchMock.mock.calls.find(call => String(call[0]).endsWith('/api/benchmark')) as [string, { body: string }] | undefined;
    const allocateCall = fetchMock.mock.calls.find(call => String(call[0]).endsWith('/api/allocate')) as [string, { body: string }] | undefined;
    if (!benchmarkCall || !allocateCall) throw new Error('allocate and benchmark were not both requested');
    expect(benchmarkCall[1].body).toBe('{}');
    expect(Object.hasOwn(JSON.parse(benchmarkCall[1].body) as object, 'tradeoff')).toBe(false);
    expect(JSON.parse(allocateCall[1].body)).toMatchObject({ tradeoff: 0.6 });
  });
});
