import { createFileRoute } from '@tanstack/react-router';
import { ResearchPage, pageHead } from '@/features/pgara/workspace';
export const Route = createFileRoute('/interference-graph')({
  head: () => pageHead('Interference Graph', 'PGARA interference graph: an academic workspace for profile-guided adaptive register allocation with clearly labeled illustrative sample data.'),
  component: Page,
});
function Page() { return <ResearchPage view="graph"/>; }
