import { createContext, useContext, useState, type ReactNode } from 'react';
import { algorithms, initialProfiles, sampleProgram, validateExperiment, type AlgorithmId, type ExperimentResult } from './types';
import { getSampleResult } from './sample-data';
import { defaultApiSettings, runExperiment, type ApiSettings } from '@/services/pgara-api';
function useExperimentState() {
  const [program, setProgram] = useState(sampleProgram);
  const [registers, setRegisters] = useState(4);
  const [profiles, setProfiles] = useState(initialProfiles);
  const [selected, setSelected] = useState<AlgorithmId[]>(algorithms.map(a => a.id));
  const [robustness, setRobustness] = useState(0.6);
  const [settings, setSettings] = useState<ApiSettings>(defaultApiSettings);
  const request = { program, registers, profiles, algorithms:selected, robustness };
  const [result, setResult] = useState<ExperimentResult | null>(() => getSampleResult(request));
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [hasRun, setHasRun] = useState(false);
  const [dirty, setDirty] = useState(false);
  function update<T>(setter: (value:T) => void, value:T) { setter(value); setDirty(true); }
  async function run() {
    const validation = validateExperiment(request);
    setErrors(validation);
    if (validation.length) return;
    setLoading(true); setResult(null);
    try { const response = await runExperiment(request, settings); setResult(response); setHasRun(true); setDirty(false); }
    catch(error) { setErrors([error instanceof Error ? error.message : 'The experiment could not be completed.']); }
    finally { setLoading(false); }
  }
  return { program,setProgram,registers,setRegisters,profiles,setProfiles,selected,setSelected,robustness,setRobustness,settings,setSettings,result,loading,errors,hasRun,dirty,update,run,setResult };
}
type ExperimentState = ReturnType<typeof useExperimentState>;
const ExperimentContext = createContext<ExperimentState | null>(null);
export function ExperimentProvider({ children }: {children:ReactNode}) { const value=useExperimentState(); return <ExperimentContext.Provider value={value}>{children}</ExperimentContext.Provider>; }
export function useExperiment() { const state=useContext(ExperimentContext); if (!state) throw new Error('ExperimentProvider is required.'); return state; }
