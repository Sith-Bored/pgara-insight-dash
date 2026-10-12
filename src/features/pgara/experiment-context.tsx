import { createContext, useContext, useState, type ReactNode } from 'react';
import { algorithms, initialProfiles, sampleProgram, validateExperiment, type AlgorithmId, type ExperimentResult } from './types';
import { getSampleResult } from './sample-data';
import { defaultApiSettings, fetchHealth, fetchSampleProgram, runBenchmark, runExperiment, type ApiSettings } from '@/services/pgara-api';
import type { BenchmarkSuite, HealthStatus } from '@/services/pgara-backend';

function useExperimentState() {
  const [program, setProgram] = useState(sampleProgram);
  const [registers, setRegisters] = useState(4);
  const [profiles, setProfiles] = useState(initialProfiles);
  const [selected, setSelected] = useState<AlgorithmId[]>(algorithms.map(a => a.id));
  const [robustness, setRobustness] = useState(0.6);
  const [settings, setSettings] = useState<ApiSettings>(defaultApiSettings);
  const request = { program, registers, profiles, algorithms: selected, robustness };
  const [result, setResult] = useState<ExperimentResult | null>(() => getSampleResult(request));
  const [loading, setLoading] = useState(false);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [hasRun, setHasRun] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [health, setHealth] = useState<HealthStatus>({ state: 'ok', message: 'Sample data is illustrative and is not a backend result.' });
  const [benchmark, setBenchmark] = useState<BenchmarkSuite | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<{ registers: number; robustness: number } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function update<T>(setter: (value: T) => void, value: T) { setter(value); setDirty(true); }

  async function applySettings(next: ApiSettings) {
    setSettings(next);
    setErrors([]);
    setNotice(null);
    if (next.mode === 'sample') {
      setHealth({ state: 'ok', message: 'Sample data is illustrative and is not a backend result.' });
      setResult(getSampleResult(request));
      setBenchmark(null);
      setBenchmarkError(null);
      setSubmitted(null);
      setDirty(false);
      setHasRun(false);
      return;
    }
    setResult(null);
    setBenchmark(null);
    setBenchmarkError(null);
    setSubmitted(null);
    setHasRun(false);
    setDirty(true);
    setHealth({ state: 'checking' });
    setHealth(await fetchHealth(next.baseUrl));
  }

  async function refreshHealth() {
    if (settings.mode !== 'backend') return;
    setHealth({ state: 'checking' });
    setHealth(await fetchHealth(settings.baseUrl));
  }

  async function loadSample() {
    if (settings.mode === 'sample') {
      setProgram(sampleProgram);
      setProfiles(initialProfiles);
      setRegisters(4);
      setRobustness(0.6);
      setNotice('Restored the illustrative dashboard program. Sample metrics stay fixed until you switch to the backend and run.');
      setDirty(true);
      setErrors([]);
      return;
    }
    setLoading(true);
    setErrors([]);
    try {
      const sample = await fetchSampleProgram(settings.baseUrl);
      setProgram(sample.source);
      setRegisters(sample.numRegisters);
      setProfiles(sample.profiles);
      setRobustness(sample.tradeoff);
      setNotice(`Loaded “${sample.name}” from GET /api/sample-program (${sample.numRegisters} register${sample.numRegisters === 1 ? '' : 's'}, tradeoff ${sample.tradeoff}). ${sample.note} Run the experiment to allocate.`);
      setDirty(true);
    } catch (error) {
      setErrors([error instanceof Error ? error.message : 'The sample program could not be loaded.']);
    } finally {
      setLoading(false);
    }
  }

  async function run() {
    const validation = validateExperiment(request);
    setErrors(validation);
    if (validation.length) return;
    setLoading(true);
    setResult(null);
    setBenchmark(null);
    setBenchmarkError(null);
    try {
      const response = await runExperiment(request, settings);
      setResult(response);
      setHasRun(true);
      setDirty(false);
      setSubmitted({ registers: request.registers, robustness: request.robustness });
      if (settings.mode === 'sample') setNotice(null);
    } catch (error) {
      setErrors([error instanceof Error ? error.message : 'The experiment could not be completed.']);
      return;
    } finally {
      setLoading(false);
    }
    if (settings.mode !== 'backend') return;
    setBenchmarkLoading(true);
    try {
      setBenchmark(await runBenchmark(settings.baseUrl, request.robustness));
      setBenchmarkError(null);
    } catch (error) {
      setBenchmark(null);
      setBenchmarkError(error instanceof Error ? error.message : 'The synthetic benchmark suite could not be loaded.');
    } finally {
      setBenchmarkLoading(false);
    }
  }

  return {
    program, setProgram, registers, setRegisters, profiles, setProfiles, selected, setSelected, robustness, setRobustness,
    settings, setSettings, result, loading, benchmarkLoading, errors, hasRun, dirty, health, benchmark, benchmarkError,
    submitted, notice, update, run, setResult, applySettings, refreshHealth, loadSample,
  };
}

type ExperimentState = ReturnType<typeof useExperimentState>;
const ExperimentContext = createContext<ExperimentState | null>(null);
export function ExperimentProvider({ children }: { children: ReactNode }) {
  const value = useExperimentState();
  return <ExperimentContext.Provider value={value}>{children}</ExperimentContext.Provider>;
}
export function useExperiment() {
  const state = useContext(ExperimentContext);
  if (!state) throw new Error('ExperimentProvider is required.');
  return state;
}
