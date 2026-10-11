import { createFileRoute } from '@tanstack/react-router';
import { ResearchPage, pageHead } from '@/features/pgara/workspace';
export const Route = createFileRoute('/')({
  head: () => pageHead('Research Overview', 'PGARA research overview: an academic workspace for profile-guided adaptive register allocation with clearly labeled illustrative sample data.'),
  component: Page,
});
function Page() { return <ResearchPage view="overview"/>; }
