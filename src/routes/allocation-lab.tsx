import { createFileRoute } from '@tanstack/react-router';
import { ResearchPage, pageHead } from '@/features/pgara/workspace';
export const Route = createFileRoute('/allocation-lab')({
  head: () => pageHead('Allocation Lab', 'PGARA allocation lab: an academic workspace for profile-guided adaptive register allocation with clearly labeled illustrative sample data.'),
  component: Page,
});
function Page() { return <ResearchPage view="lab"/>; }
