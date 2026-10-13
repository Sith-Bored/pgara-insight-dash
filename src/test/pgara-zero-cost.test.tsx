import { useEffect } from 'react';

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExperimentProvider, useExperiment } from '@/features/pgara/experiment-context';
import { spillChartScale } from '@/features/pgara/visualizations';
import { ResearchPage } from '@/features/pgara/workspace';
import type { AlgorithmId, AlgorithmResult, ExperimentResult } from '@/features/pgara/types';

function Show({ result }: { result: ExperimentResult }) {
  const { setResult, setSettings } = useExperiment();
  useEffect(() => {
    setSettings({ mode: 'backend', baseUrl: 'http://127.0.0.1:8741' });
    setResult(result);
  }, [result, setResult, setSettings]);
  return <ResearchPage view="overview" />;
}

function allocation(algorithm: AlgorithmId, physical: string | null, spills: string[], ops: number, profileOps: number[]): AlgorithmResult {
  return {
    algorithm,
    assignments: [
      { virtual: 'a', physical, liveRange: 'B0:0–B3:0', weight: 10 },
      { virtual: 'd', physical: spills.includes('d') ? null : 'p1', liveRange: 'B0:1–B3:0', weight: 4 },
    ],
    spills,
    dynamicSpillOps: ops,
    executionMs: 0.2,
    profileCosts: ['Hot loop', 'Balanced', 'Cold-heavy'].map((profile, index) => ({ profile, spillOps: profileOps[index] ?? 0 })),
  };
}

const zeroResult: ExperimentResult = {
  source: 'backend',
  results: [
    allocation('static', 'p0', [], 0, [0, 0, 0]),
    allocation('weighted', 'p0', [], 0, [0, 0, 0]),
    allocation('game', 'p0', [], 0, [0, 0, 0]),
  ],
  graph: { nodes: [{ id: 'a', x: 10, y: 10, register: 0 }], edges: [] },
  trace: [],
};

const mixedResult: ExperimentResult = {
  source: 'backend',
  results: [
    allocation('static', 'p0', [], 0, [0, 0, 0]),
    allocation('weighted', 'p0', ['d'], 3000, [1000, 1000, 1000]),
    allocation('game', 'p0', ['c', 'd', 't2', 't4'], 16550, [5850, 5500, 5200]),
  ],
  graph: { nodes: [{ id: 'a', x: 10, y: 10, register: 0 }], edges: [] },
  trace: [],
};

describe('zero and mixed spill charts', () => {
  it('keeps a zero axis from collapsing without raising the bar value', () => {
    expect(spillChartScale([0, 0, 0])).toEqual({ allZero: true, domain: [0, 1], ticks: [0] });
    expect(spillChartScale([0, 3000, 16550])).toEqual({ allZero: false, domain: [0, 'dataMax'], ticks: undefined });
  });

  it('states that an all-zero backend result has no estimated spills', async () => {
    render(<ExperimentProvider><Show result={zeroResult} /></ExperimentProvider>);
    expect(await screen.findByText('No estimated spills for this configuration.')).toBeInTheDocument();
    expect(screen.getByText('Lowest estimated spill cost').closest('.metric')).toHaveTextContent('0ops');
    expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    expect(screen.getByText(/0 spilled · 0 estimated spill ops/)).toBeInTheDocument();
    expect(screen.queryByText('4,200')).not.toBeInTheDocument();
  });

  it('keeps positive bars scaled to the returned costs when one algorithm is zero', async () => {
    render(<ExperimentProvider><Show result={mixedResult} /></ExperimentProvider>);
    expect((await screen.findAllByText('16,550')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('3,000').length).toBeGreaterThan(0);
    expect(screen.queryByText('No estimated spills for this configuration.')).not.toBeInTheDocument();
    expect(screen.getByText('Lowest estimated spill cost').closest('.metric')).toHaveTextContent('0ops');
    expect(screen.getByText(/4 spilled · 16,550 estimated spill ops/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Assignment algorithm'), { target: { value: 'static' } });
    expect(screen.getByText(/0 spilled · 0 estimated spill ops/)).toBeInTheDocument();
    expect(screen.getByText('3,000')).toBeInTheDocument();
    expect(screen.getByText('16,550')).toBeInTheDocument();
  });
});
