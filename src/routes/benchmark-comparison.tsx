import { createFileRoute } from '@tanstack/react-router';
import { ResearchPage, pageHead } from '@/features/pgara/workspace';
export const Route = createFileRoute('/benchmark-comparison')({
  head: () => pageHead('Benchmark Comparison', 'PGARA benchmark comparison: an academic workspace for profile-guided adaptive register allocation with clearly labeled illustrative sample data.'),
  component: Page,
});
function Page() { return <ResearchPage view="benchmarks"/>; }
