import React, { lazy, Suspense } from 'react';
import { InfoCard } from '../../InfoCard';

// Lazy: the graph pulls in a canvas renderer that no other section needs.
const ConnectionGraph = lazy(() =>
    import('../../graph/ConnectionGraph').then((m) => ({ default: m.ConnectionGraph })),
);

interface ConnectionsSectionProps {
    ico: string;
}

export const ConnectionsSection: React.FC<ConnectionsSectionProps> = ({ ico }) => (
    <InfoCard title="Prepojenia osôb a firiem" icon="fa-project-diagram" noPadding>
        <Suspense fallback={
            <div className="flex items-center justify-center h-32 text-gray-500 dark:text-gray-400">
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2" />
                Načítavam...
            </div>
        }>
            <ConnectionGraph ico={ico} />
        </Suspense>
    </InfoCard>
);
