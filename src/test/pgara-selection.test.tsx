import { useEffect } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExperimentProvider, useExperiment } from '@/features/pgara/experiment-context';
import { Assignments, DecisionTrace } from '@/features/pgara/visualizations';
import type { AlgorithmId, ExperimentResult } from '@/features/pgara/types';

function row(virtual: string) {
  const cell = screen.getByText(virtual);
  const line = cell.closest('tr');
  if (!line) throw new Error(`missing row for ${virtual}`);
  return line;
}

function Show({ result }: { result: ExperimentResult }) {
  const { setResult } = useExperiment();
  useEffect(() => { setResult(result); }, [result, setResult]);
  return <><Assignments /><DecisionTrace /></>;
}

describe('algorithm selection and trace', () => {
  it('switches sample allocations and keeps the trace labeled illustrative', () => {
    render(<ExperimentProvider><Assignments /><DecisionTrace /></ExperimentProvider>);
    expect(screen.getByLabelText('Assignment algorithm')).toHaveValue('game');
    expect(row('t4')).toHaveTextContent('Spilled');
    expect(screen.getByText(/1,200 illustrative spill ops/)).toBeInTheDocument();
    expect(screen.getAllByText('Illustrative sequence').length).toBeGreaterThan(0);
    expect(screen.getByText('Initialize allocation')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Assignment algorithm'), { target: { value: 'static' } });
    expect(row('t4')).not.toHaveTextContent('Spilled');
    expect(row('t2')).toHaveTextContent('Spilled');
    expect(row('t5')).toHaveTextContent('Spilled');
    expect(screen.getByText(/4,200 illustrative spill ops/)).toBeInTheDocument();
    expect(screen.getByText('0.42 ms')).toBeInTheDocument();
  });

  it('recognizes a potential_game result and shows its backend trace', async () => {
    render(<ExperimentProvider><Show result={backendResult} /></ExperimentProvider>);
    expect(await screen.findByText('Move b from spill to p0')).toBeInTheDocument();
    expect(screen.getAllByText('Local equilibrium').length).toBeGreaterThan(0);
    expect(screen.queryByText('Illustrative sequence')).not.toBeInTheDocument();
    expect(screen.queryByText('Initialize allocation')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Assignment algorithm')).toHaveValue('game');
    expect(row('a')).toHaveTextContent('Spilled');
    expect(screen.getByText(/20 estimated spill ops/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Assignment algorithm'), { target: { value: 'static' } });
    expect(row('a')).toHaveTextContent('p0');
    expect(screen.getByText(/19 estimated spill ops/)).toBeInTheDocument();
    expect(screen.getByText('0.11 ms')).toBeInTheDocument();
    expect(screen.getByText('Move b from spill to p0')).toBeInTheDocument();
  });

  it('still switches when two algorithms share an allocation', async () => {
    render(<ExperimentProvider><Show result={sameAllocation} /></ExperimentProvider>);
    expect(await screen.findByText('0.20 ms')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Assignment algorithm'), { target: { value: 'weighted' } });
    expect(row('a')).toHaveTextContent('p0');
    expect(screen.getByText('0.90 ms')).toBeInTheDocument();
    expect(screen.getByText(/19 estimated spill ops/)).toBeInTheDocument();
  });
});

function allocation(algorithm: AlgorithmId, physical: string | null, spills: string[], ops: number, ms: number) {
  return {
    algorithm,
    assignments: [{ virtual: 'a', physical, liveRange: 'def_a:0', weight: 10 }],
    spills,
    dynamicSpillOps: ops,
    executionMs: ms,
    profileCosts: [{ profile: 'skew', spillOps: ops }],
  };
}

const backendResult: ExperimentResult = {
  source: 'backend',
  results: [
    allocation('static', 'p0', ['b'], 19, 0.11),
    { ...allocation('game', null, ['a'], 20, 0.2), algorithm: 'potential_game' as AlgorithmId },
  ],
  graph: { nodes: [], edges: [] },
  trace: [{ step: 1, action: 'Move b from spill to p0', detail: 'accepted a strictly lower potential', potential: 10, status: 'Accepted' }],
  traceStatus: 'no_improving_move',
};

const sameAllocation: ExperimentResult = {
  source: 'backend',
  results: [
    allocation('static', 'p0', ['b'], 19, 0.2),
    allocation('weighted', 'p0', ['b'], 19, 0.9),
  ],
  graph: { nodes: [], edges: [] },
  trace: [],
};
