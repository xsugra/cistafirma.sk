import React, {useState, useEffect} from 'react';
import {api} from '../api';
import type {NotificationEvent} from '../types';

export const NotificationCenter: React.FC = () => {
    const [events, setEvents] = useState<NotificationEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadEvents();
    }, []);

    const loadEvents = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.getNotifications();
            setEvents(data);
        } catch {
            setError('Nepodarilo sa načítať notifikácie.');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center py-16">
                <div className="w-10 h-10 border-4 border-brand border-t-transparent rounded-full animate-spin"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="app-card p-8 text-center">
                <i className="fas fa-exclamation-triangle text-red-400 text-3xl mb-3 block"></i>
                <p className="text-gray-500">{error}</p>
                <button onClick={loadEvents} className="btn btn-outline mt-4 text-sm">
                    Skúsiť znova
                </button>
            </div>
        );
    }

    if (events.length === 0) {
        return (
            <div className="app-card p-8 text-center">
                <i className="far fa-bell text-gray-300 text-5xl mb-4 block"></i>
                <p className="text-gray-500 text-lg">Žiadne notifikácie</p>
                <p className="text-gray-400 text-sm mt-1">Zatiaľ nemáte žiadne upozornenia.</p>
            </div>
        );
    }

    const getEventIcon = (type: string) => {
        switch (type) {
            case 'debt_change':
                return 'fa-coins text-yellow-500';
            case 'status_change':
                return 'fa-flag text-blue-500';
            case 'executive_change':
                return 'fa-user-tie text-purple-500';
            default:
                return 'fa-circle-info text-gray-400';
        }
    };

    return (
        <div className="space-y-3">
            {events.map((event) => (
                <div
                    key={event.id}
                    className="app-card p-4 flex items-start gap-4 animate-fade-in hover:shadow-md transition-shadow"
                >
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-gray-100 dark:bg-slate-800`}>
                        <i className={`fas ${getEventIcon(event.eventType)} text-lg`}></i>
                    </div>
                    <div className="flex-grow min-w-0">
                        <div className="flex items-start justify-between gap-2">
                            <h4 className="font-semibold text-gray-900 dark:text-white truncate">
                                {event.title}
                            </h4>
                            {!event.sentEmail && (
                                <span className="badge badge-warning text-[10px] flex-shrink-0">
                                    Neodoslané
                                </span>
                            )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                            {event.companyName} · {event.eventTypeDisplay}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                            {new Date(event.createdAt).toLocaleString('sk-SK')}
                        </p>
                    </div>
                </div>
            ))}
        </div>
    );
};
