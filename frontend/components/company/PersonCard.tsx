import React from 'react';
import type { OrsrPerson } from '../../types';
import { InfoCard } from '../InfoCard';
import { displayName } from './helpers';

const ACCENT_MAP: Record<string, string> = {
    blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-500/30 text-blue-600 dark:text-blue-400',
    sky: 'bg-sky-50 dark:bg-sky-900/20 border-sky-200 dark:border-sky-500/30 text-sky-600 dark:text-sky-400',
    green: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-500/30 text-green-600 dark:text-green-400',
    amber: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-500/30 text-amber-600 dark:text-amber-400',
    purple: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-500/30 text-purple-600 dark:text-purple-400',
    rose: 'bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-500/30 text-rose-600 dark:text-rose-400',
};

export type Accent = 'blue' | 'purple' | 'amber' | 'green' | 'rose' | 'sky';

export const PersonCard: React.FC<{
    person: OrsrPerson;
    accent: Accent;
    icon: string;
}> = ({ person, accent, icon }) => {
    const name = displayName(person);
    return (
        <div className={`p-3 rounded-lg border ${ACCENT_MAP[accent]}`}>
            <div className="flex items-start gap-3">
                <i className={`fas ${icon} mt-1`}></i>
                <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white break-words">{name}</p>
                    {person.role && (
                        <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mt-0.5">
                            {person.role}
                        </p>
                    )}
                    {person.address && (
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                            <i className="fas fa-map-marker-alt mr-2 text-gray-400"></i>
                            {person.address}
                        </p>
                    )}
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {person.vznik_funkcie && (
                            <span><i className="fas fa-calendar-plus mr-1"></i>Vznik funkcie: {person.vznik_funkcie}</span>
                        )}
                        {person.person_ico && (
                            <span><i className="fas fa-hashtag mr-1"></i>IČO: {person.person_ico}</span>
                        )}
                        {person.ine_id && (
                            <span><i className="fas fa-id-card mr-1"></i>{person.ine_id}</span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export const PeopleSection: React.FC<{
    title: string;
    icon: string;
    people: OrsrPerson[];
    accent: Accent;
    personIcon: string;
    emptyLabel: string;
    subtitle?: string;
}> = ({ title, icon, people, accent, personIcon, emptyLabel, subtitle }) => (
    <InfoCard title={title} icon={icon}>
        {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 italic">{subtitle}</p>
        )}
        {people.length > 0 ? (
            <div className="space-y-3">
                {people.map((person, idx) => (
                    <PersonCard key={`${person.name}-${idx}`} person={person} accent={accent} icon={personIcon} />
                ))}
            </div>
        ) : (
            <div className="text-center py-4 text-gray-500 dark:text-gray-400">
                <i className="fas fa-info-circle mr-2"></i>{emptyLabel}
            </div>
        )}
    </InfoCard>
);
