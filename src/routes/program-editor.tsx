import { createFileRoute } from '@tanstack/react-router';
import { ResearchPage, pageHead } from '@/features/pgara/workspace';
export const Route = createFileRoute('/program-editor')({
  head: () => pageHead('Program Editor', 'PGARA program editor: an academic workspace for profile-guided adaptive register allocation with clearly labeled illustrative sample data.'),
  component: Page,
});
function Page() { return <ResearchPage view="editor"/>; }
