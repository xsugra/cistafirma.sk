
import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { PersonCoverage, PersonSummary } from '../types';
import { personPath } from '../constants';
import { PersonCoverageNote } from './person/PersonCoverageNote';
import { RoleStateBadge } from './person/RoleStateBadge';

/**
 * One debounced answer, both halves of it.
 *
 * Companies and people come from two endpoints and are two separate lists, but
 * they answer one keystroke and are cached under one key, so that a query is
 * never half-remembered.
 */
interface SuggestionBundle {
  companies: any[];
  persons: PersonSummary[];
  /**
   * `null` means the person endpoint did not answer -- which is not the same as
   * an answer of "nobody", and is exactly why the coverage sentence has a
   * wording for its absence.
   */
  personCoverage: PersonCoverage | null;
  personDetail: string | null;
}

const EMPTY_BUNDLE: SuggestionBundle = {
  companies: [],
  persons: [],
  personCoverage: null,
  personDetail: null,
};

/**
 * Two sizes of one box, with one behaviour.
 *
 * `hero` is the pill on the home and search pages, where finding a firm is what
 * the page is for. `compact` is the same box standing above a firm or a person,
 * where the page already has a subject and the box is only how the reader
 * changes it -- so it is sized as a tool rather than as a headline. The
 * difference is padding, a shorter placeholder and a shorter button word;
 * everything else -- the debounce, the two-character floor, the two endpoints,
 * the suggestion rows -- is shared deliberately.
 */
export type SearchBarVariant = 'hero' | 'compact';

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  initialIco: string;
  variant?: SearchBarVariant;
}

const VARIANT_STYLES = {
  hero: {
    wrapper: 'relative w-full px-4 sm:px-0',
    frame: 'border-2 border-gray-200 dark:border-slate-800 rounded-full shadow-lg',
    icon: 'pl-4 sm:pl-6 pr-2 sm:pr-3 text-lg sm:text-xl',
    input: 'text-base sm:text-lg py-3 sm:py-4 pr-24 sm:pr-36',
    button: 'right-1.5 sm:right-2 py-2 sm:py-3 px-4 sm:px-8 text-sm sm:text-base',
    dropdown: 'mt-2 mx-4 sm:mx-0',
    placeholder: 'Zadajte IČO, názov firmy alebo meno osoby...',
    label: 'Overiť',
  },
  compact: {
    // No side padding here on purpose: this one is placed inside a page that
    // already has its own gutter, and a second one would inset the box from the
    // content it stands above. The hero's `px-4` is compensated for in its own
    // dropdown and button offsets, which is why the two wrappers cannot simply
    // share a class list.
    wrapper: 'relative w-full',
    frame: 'border border-gray-300 dark:border-slate-700 rounded-full shadow-sm',
    icon: 'pl-4 pr-2 text-base',
    input: 'text-sm py-2.5 pr-24',
    button: 'right-1 py-2 px-4 text-sm',
    dropdown: 'mt-2',
    placeholder: 'Hľadať inú firmu alebo osobu…',
    label: 'Hľadať',
  },
} as const;

export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  isLoading,
  initialIco,
  variant = 'hero',
}) => {
  const styles = VARIANT_STYLES[variant];
  const [query, setQuery] = useState(initialIco);
  const [suggestions, setSuggestions] = useState<SuggestionBundle>(EMPTY_BUNDLE);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isFocused = useRef(false);
  const autocompleteRequestRef = useRef<{ query: string; controller: AbortController } | null>(null);
  const autocompleteCacheRef = useRef(new Map<string, SuggestionBundle>());

  useEffect(() => {
    setQuery(initialIco);
  }, [initialIco]);

  // Handle click outside to close suggestions
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Autocomplete logic with debounce
  useEffect(() => {
    const trimmedQuery = query.trim();
    const normalizedQuery = trimmedQuery.toLocaleLowerCase();
    const activeRequest = autocompleteRequestRef.current;

    if (activeRequest && activeRequest.query !== normalizedQuery) {
      activeRequest.controller.abort();
      autocompleteRequestRef.current = null;
    }

    if (trimmedQuery.length < 2) {
      setSuggestions(EMPTY_BUNDLE);
      setIsSearching(false);
      return;
    }

    const cachedSuggestions = autocompleteCacheRef.current.get(normalizedQuery);
    if (cachedSuggestions) {
      setSuggestions(cachedSuggestions);
      if (isFocused.current) setShowSuggestions(true);
      setIsSearching(false);
      return;
    }

    if (autocompleteRequestRef.current?.query === normalizedQuery) {
      return;
    }

    const fetchSuggestions = async () => {
      const controller = new AbortController();
      autocompleteRequestRef.current = { query: normalizedQuery, controller };
      setIsSearching(true);
      try {
        // Both halves are asked together and swallowed separately: a failure on
        // one must not empty the other, and a suggestion list that disappears
        // because a second request failed is worse than a short one. Nothing
        // here reaches the register -- see `OrsrRegisterGroup` for the one call
        // that does, and why it is behind a button.
        const [companyData, personData] = await Promise.all([
          api.searchCompanies(trimmedQuery, { signal: controller.signal }).catch((e) => {
            if ((e as Error)?.name !== 'AbortError') console.error('Autocomplete error', e);
            return { results: [] };
          }),
          api.searchPersons(trimmedQuery, undefined, { signal: controller.signal }).catch((e) => {
            if ((e as Error)?.name !== 'AbortError') console.error('Autocomplete error (osoby)', e);
            return null;
          }),
        ]);
        if (controller.signal.aborted || autocompleteRequestRef.current?.controller !== controller) return;
        const bundle: SuggestionBundle = {
          companies: companyData?.results || [],
          persons: personData?.results ?? [],
          personCoverage: personData?.coverage ?? null,
          personDetail: personData?.detail ?? null,
        };
        autocompleteCacheRef.current.set(normalizedQuery, bundle);
        setSuggestions(bundle);
        if (isFocused.current) setShowSuggestions(true);
      } catch (e) {
        if (controller.signal.aborted || (e as Error)?.name === 'AbortError') return;
        console.error("Autocomplete error", e);
      } finally {
        if (autocompleteRequestRef.current?.controller === controller) {
          autocompleteRequestRef.current = null;
          setIsSearching(false);
        }
      }
    };

    const timer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => () => {
    autocompleteRequestRef.current?.controller.abort();
    autocompleteRequestRef.current = null;
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuery = query.trim();
    setShowSuggestions(false);
    onSearch(trimmedQuery);
  };

  const handleSelectSuggestion = (item: any) => {
    setQuery(item.ico);
    setShowSuggestions(false);
    onSearch(item.ico);
  };

  const companies = suggestions.companies;
  const persons = suggestions.persons;
  const hasResults = companies.length > 0 || persons.length > 0;
  // The person block is drawn alongside the companies whenever the dropdown is
  // open at all -- including when it found nobody, which is the common case.
  // Our person graph covers a fragment of the register, so an empty list here
  // is usually "we have not read those companies", and the coverage sentence
  // under it is what says so. It is not drawn on its own: a dropdown opening on
  // every keystroke only to report that a name has no relations would be noise.
  const showPersons = persons.length > 0 || companies.length > 0;

  return (
    <div className={styles.wrapper} ref={dropdownRef}>
      <form onSubmit={handleSubmit}>
        <div className={`flex items-center bg-white dark:bg-slate-900 overflow-hidden focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-200 dark:focus-within:ring-blue-900 transition-all duration-300 ${styles.frame}`}>
          <i className={`fas fa-search text-gray-400 ${styles.icon}`}></i>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => { isFocused.current = true; if (query.length >= 2 && hasResults) setShowSuggestions(true); }}
            onBlur={() => { isFocused.current = false; }}
            placeholder={styles.placeholder}
            aria-label="Hľadať firmu alebo osobu"
            className={`w-full bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none ${styles.input}`}
            disabled={isLoading}
          />
          <button
            type="submit"
            className={`absolute top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold rounded-full transition-transform hover:scale-105 active:scale-95 shadow-md ${styles.button}`}
            disabled={isLoading}
          >
            {isLoading || isSearching ? <i className="fas fa-circle-notch animate-spin"></i> : styles.label}
          </button>
        </div>
      </form>

      {/* Suggestions Dropdown */}
      {showSuggestions && hasResults && (
        <div className={`absolute left-0 right-0 bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden z-[100] animate-fade-in ${styles.dropdown}`}>
          <div className="max-h-[420px] overflow-y-auto">
            {companies.length > 0 && (
              <>
                <p className="px-6 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                  Firmy
                </p>
                {companies.map((item) => (
                  <div
                    key={item.ico}
                    onClick={() => handleSelectSuggestion(item)}
                    className="px-6 py-3 hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer flex justify-between items-center group transition-colors border-b border-gray-50 dark:border-slate-800/50 last:border-0"
                  >
                    <div className="flex-grow min-w-0 mr-4">
                      <p className="font-bold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400">
                        {item.nazov_UJ}
                      </p>
                      <p className="text-xs text-gray-500 flex gap-2">
                        <span className="font-mono">IČO: {item.ico}</span>
                        <span>•</span>
                        <span className="truncate">{item.mesto}</span>
                      </p>
                    </div>
                    <div className="flex-shrink-0">
                       <span className="text-[10px] px-2 py-0.5 rounded bg-gray-100 dark:bg-slate-800 text-gray-500 uppercase font-bold">
                         {item.legal_form_short || 'Firma'}
                       </span>
                    </div>
                  </div>
                ))}
              </>
            )}

            {/* Our own person graph. Deliberately not the register's list: that
                one lives on the person's page behind a button, because it is a
                different claim about the same name and because typing must never
                reach a third-party server. */}
            {showPersons && (
              <div className="border-t border-gray-100 bg-gray-50/60 dark:border-slate-800 dark:bg-slate-950/40">
                <p className="px-6 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                  Osoby u nás
                </p>

                {persons.length > 0 ? (
                  persons.map((person) => {
                    const first = person.companies[0];
                    const rest = person.companies.length - 1;
                    return (
                      <Link
                        key={person.id}
                        to={personPath(person.id)}
                        onClick={() => setShowSuggestions(false)}
                        className="px-6 py-3 hover:bg-blue-50 dark:hover:bg-blue-900/20 flex justify-between items-center gap-4 group transition-colors border-b border-gray-100/70 dark:border-slate-800/50 last:border-0"
                      >
                        <div className="flex-grow min-w-0">
                          <p className="font-bold text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400">
                            {person.name}
                          </p>
                          {first && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                              {first.role_display ? `${first.role_display} · ` : ''}
                              {first.name}
                              {rest > 0 ? ` a ďalšie ${rest}` : ''}
                            </p>
                          )}
                        </div>
                        {first && <RoleStateBadge isActive={first.is_active} />}
                      </Link>
                    );
                  })
                ) : (
                  <p className="px-6 py-3 text-xs text-gray-500 dark:text-gray-400">
                    {suggestions.personDetail ||
                      'V našich dátach sme k tomuto menu nikoho nenašli.'}
                  </p>
                )}

                <div className="border-t border-gray-100 px-6 py-2.5 dark:border-slate-800/60">
                  <PersonCoverageNote coverage={suggestions.personCoverage} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
