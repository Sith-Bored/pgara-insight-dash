import { z } from 'zod';
import type { ExperimentRequest, ExperimentResult } from '@/features/pgara/types';
import { getSampleResult } from '@/features/pgara/sample-data';
const resultSchema = z.object({
  source: z.enum(['sample', 'backend']),
  results: z.array(z.object({ algorithm: z.enum(['static','weighted','game']), assignments: z.array(z.object({ virtual:z.string(), physical:z.string().nullable(), liveRange:z.string(), weight:z.number().nonnegative() })), spills:z.array(z.string()), dynamicSpillOps:z.number().nonnegative(), executionMs:z.number().nonnegative(), profileCosts:z.array(z.object({profile:z.string(),spillOps:z.number().nonnegative()})) })),
  graph: z.object({nodes:z.array(z.object({id:z.string(),x:z.number(),y:z.number(),register:z.number().nullable()})),edges:z.array(z.tuple([z.string(),z.string()]))}),
  trace:z.array(z.object({step:z.number(),action:z.string(),detail:z.string(),potential:z.number(),status:z.string()})),
});
export interface ApiSettings { mode: 'sample' | 'backend'; baseUrl: string }
export const defaultApiSettings: ApiSettings = { mode:'sample', baseUrl: import.meta.env.VITE_PGARA_API_URL || 'http://localhost:8000' };
export async function runExperiment(request: ExperimentRequest, settings: ApiSettings): Promise<ExperimentResult> {
  if (settings.mode === 'sample') { await new Promise(resolve => setTimeout(resolve, 850)); return getSampleResult(request); }
  let url: URL;
  try { url = new URL(settings.baseUrl); if (!['http:', 'https:'].includes(url.protocol)) throw new Error(); }
  catch { throw new Error('Enter a valid HTTP or HTTPS backend URL in connection settings.'); }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${url.href.replace(/\/$/, '')}/api/allocate`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(request), signal:controller.signal });
    if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. Check the service and try again.`);
    const data = resultSchema.safeParse(await response.json());
    if (!data.success) throw new Error('The backend response does not match the PGARA experiment contract.');
    if (data.data.results.some(r => !request.algorithms.includes(r.algorithm))) throw new Error('The backend returned an algorithm that was not requested.');
    return { ...data.data, source:'backend' };
  } catch(error) {
    if (error instanceof TypeError) throw new Error('Cannot connect to the analysis backend. Check its URL, availability, and CORS settings, or switch to sample mode.');
    if (error instanceof Error && error.name === 'AbortError') throw new Error('The backend did not respond within 15 seconds. Try again when it is available.');
    throw error;
  } finally { clearTimeout(timeout); }
}
