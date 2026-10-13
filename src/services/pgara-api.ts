import type { AlgorithmId, ExperimentRequest, ExperimentResult } from '@/features/pgara/types';
import { getSampleResult } from '@/features/pgara/sample-data';
import {
  DEFAULT_BACKEND_URL,
  allocateBody,
  allocateResponseSchema,
  apiUrl,
  benchmarkResponseSchema,
  healthResponseSchema,
  mapAllocateResponse,
  toUiAlgorithm,
  mapBenchmarkResponse,
  mapSampleProgram,
  readBackendError,
  sampleResponseSchema,
  type AllocateResponse,
  type BenchmarkSuite,
  type HealthStatus,
  type LoadedSample,
} from '@/services/pgara-backend';

export interface ApiSettings { mode: 'sample' | 'backend'; baseUrl: string }

export const defaultApiSettings: ApiSettings = {
  mode: 'sample',
  baseUrl: import.meta.env['VITE_PGARA_API_URL'] || DEFAULT_BACKEND_URL,
};

export async function runExperiment(request: ExperimentRequest, settings: ApiSettings): Promise<ExperimentResult> {
  if (settings.mode === 'sample') {
    await new Promise(resolve => setTimeout(resolve, 850));
    return getSampleResult(request);
  }
  const targets: Array<AlgorithmId | 'all'> = request.algorithms.length === 3 ? ['all'] : request.algorithms;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const parts = await Promise.all(targets.map(algorithm => postAllocate(settings.baseUrl, allocateBody(request, algorithm), controller.signal)));
    const first = parts[0];
    if (!first) throw new Error('The backend did not return an allocation.');
    const merged: AllocateResponse = { ...first, results: parts.flatMap(part => part.results) };
    const mapped = mapAllocateResponse(merged, request.algorithms);
    const ordered = request.algorithms.map(id => mapped.results.find(result => toUiAlgorithm(result.algorithm) === id));
    if (ordered.some(result => !result)) throw new Error('The backend did not return every requested algorithm.');
    return { ...mapped, results: ordered.filter((result): result is ExperimentResult['results'][number] => Boolean(result)) };
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot connect to the analysis backend. Check its URL, availability, and CORS settings, or switch to sample mode.');
    if (error instanceof Error && error.name === 'AbortError') throw new Error('The backend did not respond within 15 seconds. Try again when it is available.');
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function runBenchmark(baseUrl: string): Promise<BenchmarkSuite> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(apiUrl(baseUrl, '/api/benchmark'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(await readBackendError(response));
    const parsed = benchmarkResponseSchema.safeParse(await readJson(response));
    if (!parsed.success) throw new Error('The benchmark response does not match the PGARA API 1.0 contract.');
    return mapBenchmarkResponse(parsed.data);
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot connect to the analysis backend.');
    if (error instanceof Error && error.name === 'AbortError') throw new Error('The benchmark request did not respond within 15 seconds.');
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function fetchSampleProgram(baseUrl: string): Promise<LoadedSample> {
  const response = await fetch(apiUrl(baseUrl, '/api/sample-program'));
  if (!response.ok) throw new Error(await readBackendError(response));
  const parsed = sampleResponseSchema.safeParse(await readJson(response));
  if (!parsed.success) throw new Error('The sample-program response does not match the PGARA API 1.0 contract.');
  return mapSampleProgram(parsed.data);
}

export async function fetchHealth(baseUrl: string): Promise<HealthStatus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(apiUrl(baseUrl, '/api/health'), { signal: controller.signal });
    if (!response.ok) return { state: 'error', message: await readBackendError(response) };
    const parsed = healthResponseSchema.safeParse(await readJson(response));
    if (!parsed.success) return { state: 'error', message: 'The health response does not match API 1.0.' };
    return { state: 'ok', version: parsed.data.version, apiVersion: parsed.data.api_version, message: `Connected to ${parsed.data.service} API ${parsed.data.api_version}.` };
  } catch (error) {
    if (error instanceof Error && error.message.startsWith('Enter a valid')) return { state: 'error', message: error.message };
    if (error instanceof Error && error.name === 'AbortError') return { state: 'error', message: 'The backend did not respond within 8 seconds.' };
    return { state: 'error', message: 'Cannot connect to the analysis backend. Check its URL, availability, and CORS settings.' };
  } finally {
    clearTimeout(timeout);
  }
}

async function postAllocate(baseUrl: string, body: ReturnType<typeof allocateBody>, signal: AbortSignal): Promise<AllocateResponse> {
  const response = await fetch(apiUrl(baseUrl, '/api/allocate'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error(await readBackendError(response));
  const parsed = allocateResponseSchema.safeParse(await readJson(response));
  if (!parsed.success) throw new Error('The backend response does not match the PGARA experiment contract.');
  return parsed.data;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new Error('The backend response does not match the PGARA experiment contract.');
  }
}
