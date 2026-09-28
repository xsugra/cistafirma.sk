import React, {useCallback, useEffect, useState} from 'react';
import {Navigate, useNavigate, useSearchParams} from 'react-router-dom';
import {SearchBar} from '../components/SearchBar';
import {LoadingSpinner} from '../components/LoadingSpinner';
import {PersonCoverageNote} from '../components/person/PersonCoverageNote';
import {PersonResultRow} from '../components/person/PersonResultRow';
import {companyPath, personPath} from '../constants';
import {DEFAULT_SECTION_ID} from '../companySections';
import {api} from '../api';
import type {PersonCoverage, PersonSummary} from '../types';
import {looksLikeIco} from '../utils/ico';

/**
 * The search page. It finds a firm or a person and sends you to them.
 *
 * It used to render the firm's detail inline, which made the answer to "where
 * is this company's page" depend on how you arrived. Now there is one page per
 * firm (`/firma/:ico/:sekcia`) and this one is the way in.
 *
 * `?ico=` still works — links written before that page existed point here, and
 * a link that used to work and now doesn't is worse than either design. It is
 * read, not rendered: the query is turned into the firm's URL on arrival.
 *
 * The box above used to answer a name with the person list and this page then
 * answered the very same name with "Nenašli sa žiadne výsledky" — because only
 * the box asked the person endpoint. Both halves were always on screen
 * together; only one of them was ever asked. `handleSearch` now asks both, and
 * the two answers are merged rather than raced.
 */
export const Monitoring: React.FC = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const initialSearch = searchParams.get('ico') || '';
    const icoFromQuery = looksLikeIco(initialSearch) ? initialSearch.trim() : null;

    const [query, setQuery] = useState<string>(icoFromQuery ? '' : initialSearch);
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [personResults, setPersonResults] = useState<PersonSummary[]>([]);
    /**
     * `null` means the person endpoint did not answer — which is not an answer
     * of "nobody", and is the distinction `PersonCoverageNote` renders.
     */
    const [personCoverage, setPersonCoverage] = useState<PersonCoverage | null>(null);
    const [personDetail, setPersonDetail] = useState<string | null>(null);
    /**
     * Whether the person endpoint answered at all — which its two nullable
     * fields cannot say on their own, since a successful answer may legitimately
     * carry no counts (`PersonCoverage` explains why). Without this the page
     * cannot tell "we found nobody" from "the request failed", and the two
     * demand different sentences.
     */
    const [personAnswered, setPersonAnswered] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [showIntro, setShowIntro] = useState<boolean>(true);

    const handleSearch = useCallback(async (searchQuery: string) => {
        const trimmedQuery = searchQuery.trim();
        if (!trimmedQuery || trimmedQuery.length < 2) {
            setError('Zadajte aspoň 2 znaky (IČO, názov firmy alebo meno osoby).');
            return;
        }

        // A twelve-character IČO is a real IČO (organizational units), and a
        // six-digit one is an old IČO the register still answers for. Both used
        // to fall through to the name search and return nothing the reader
        // wanted. See `utils/ico.ts` for why the range matches the backend's.
        if (looksLikeIco(trimmedQuery)) {
            navigate(companyPath(trimmedQuery, DEFAULT_SECTION_ID));
            return;
        }

        setIsLoading(true);
        setError(null);
        setSearchResults([]);
        setPersonResults([]);
        setPersonCoverage(null);
        setPersonDetail(null);
        setPersonAnswered(false);
        setShowIntro(false);
        setQuery(trimmedQuery);

        // Both halves are asked together and swallowed separately, exactly as
        // the suggestion box does it: a failure on one must not empty the other,
        // and a person list that disappears because the company request failed
        // is worse than a short one. The person call is a plain read of our own
        // graph -- nothing here reaches the register, which stays behind the
        // button on the person's page (see `OrsrRegisterGroup`).
        const [companyData, personData] = await Promise.all([
            api.searchCompanies(trimmedQuery).catch((err) => {
                console.error('Vyhľadávanie firiem zlyhalo', err);
                return null;
            }),
            api.searchPersons(trimmedQuery).catch((err) => {
                console.error('Vyhľadávanie osôb zlyhalo', err);
                return null;
            }),
        ]);

        const companies: any[] = companyData?.results || [];
        const persons: PersonSummary[] = personData?.results ?? [];

        setSearchResults(companies);
        setPersonResults(persons);
        setPersonCoverage(personData?.coverage ?? null);
        setPersonDetail(personData?.detail ?? null);
        setPersonAnswered(personData !== null);

        if (companies.length + persons.length === 0) {
            // The old wording, kept: it is what the reader was told before, and
            // it is still true. What is new is the coverage sentence the card
            // carries below it -- an empty person list without it reads as
            // "this person is in no company", which is a claim about a person
            // and not a statement about our data.
            setError(
                companyData === null && personData === null
                    ? 'Nepodarilo sa vyhľadať. Skúste to znova.'
                    : 'Nenašli sa žiadne výsledky pre váš dopyt.',
            );
        } else if (companies.length + persons.length === 1) {
            // One hit is not a list, whichever kind it is. This is the rule the
            // page already had for a single firm; a single person now gets it
            // too, because "where does this person act" is answered by their
            // page and a list of one is a click in the way.
            if (persons.length === 1) {
                navigate(personPath(persons[0].id));
            } else {
                navigate(companyPath(companies[0].ico, DEFAULT_SECTION_ID));
            }
        }

        setIsLoading(false);
    }, [navigate]);

    // A name in `?ico=` (an old or hand-edited link) is still worth searching
    // for rather than discarding; only a real IČO redirects.
    useEffect(() => {
        if (icoFromQuery) return;
        if (initialSearch) {
            setQuery(initialSearch);
            handleSearch(initialSearch);
        }
    }, [initialSearch, icoFromQuery, handleSearch]);

    if (icoFromQuery) {
        return <Navigate to={companyPath(icoFromQuery, DEFAULT_SECTION_ID)} replace />;
    }

    // One card for one answer, whichever half of it matched. Two cards would
    // let a reader see "Výsledky vyhľadávania (0)" above a list of people.
    const hasResults = searchResults.length > 0 || personResults.length > 0;

    return (
        <div className="max-w-5xl mx-auto w-full animate-fade-in py-10">
            <div className="text-center mb-10">
                <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
                    Monitoring a Analýza
                </h1>
                <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
                    Zadajte IČO, názov spoločnosti alebo meno osoby a získajte okamžitý prístup k dátam.
                </p>
            </div>

            <div className="max-w-2xl mx-auto mb-12">
                <SearchBar onSearch={handleSearch} isLoading={isLoading} initialIco={query} />
            </div>

            <div className="min-h-[300px]">
                {isLoading && <LoadingSpinner />}

                {error && !isLoading && (
                    <div className="p-8 bg-white dark:bg-slate-900 rounded-xl border border-red-200 dark:border-red-900/50 shadow-lg text-center">
                        <i className="fas fa-exclamation-triangle text-red-500 text-3xl mb-4"></i>
                        <p className="text-red-600 dark:text-red-400 font-medium">{error}</p>
                        {/* The empty answer is exactly where the coverage
                            sentence is owed, and it is the one place it used to
                            be missing: "Nenašli sa žiadne výsledky" printed on
                            its own is a claim that the person is nowhere,
                            made by a search that never asked about people.
                            It is shown only when the person endpoint actually
                            answered -- a note about our coverage printed after
                            a request that failed would be its own false
                            statement about our data. */}
                        {personAnswered && (
                            <PersonCoverageNote coverage={personCoverage} className="mt-4 justify-center" />
                        )}
                    </div>
                )}

                {showIntro && !isLoading && !error && (
                    <div className="text-center p-12">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
                            <i className="fas fa-search text-blue-600 dark:text-blue-400 text-2xl"></i>
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">Pripravený na analýzu?</h3>
                        <p className="text-gray-600 dark:text-gray-400 text-base max-w-lg mx-auto">
                            Náš systém preveruje registre dlžníkov, finančnú správu a obchodný register v reálnom čase.
                        </p>    
                    </div>
                )}

                {hasResults && !isLoading && (
                    <div className="app-card overflow-hidden">
                        <div className="bg-gray-50 dark:bg-slate-900 px-6 py-4 border-b border-gray-100 dark:border-slate-800">
                            <h3 className="font-bold text-gray-900 dark:text-white">
                                Výsledky vyhľadávania ({searchResults.length + personResults.length})
                            </h3>
                        </div>

                        {searchResults.length > 0 && (
                            <>
                                <p className="px-6 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                                    Firmy
                                </p>
                                <div className="divide-y divide-gray-100 dark:divide-slate-800">
                                    {searchResults.map(result => (
                                        <div
                                            key={result.ico}
                                            onClick={() => handleSearch(result.ico)}
                                            className="px-6 py-4 hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer flex justify-between items-center group transition-colors"
                                        >
                                            <div>
                                                <h4 className="font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">{result.nazov_UJ}</h4>
                                                <p className="text-sm text-gray-500">IČO: {result.ico} • {result.mesto}</p>
                                            </div>
                                            <i className="fas fa-chevron-right text-gray-300 group-hover:text-blue-500 transition-colors"></i>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}

                        {/* Our own person graph, and the same one the box above
                            shows. It is drawn whenever there is any result at
                            all -- including when it found nobody, which is the
                            common case, because our graph covers a fragment of
                            the register. An empty list is usually "we have not
                            read those companies", and the coverage sentence
                            under it is what says so. */}
                        <div className="border-t border-gray-100 bg-gray-50/60 dark:border-slate-800 dark:bg-slate-950/40">
                            <p className="px-6 pt-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                                Osoby u nás
                            </p>

                            {personResults.length > 0 ? (
                                personResults.map(person => (
                                    <PersonResultRow
                                        key={person.id}
                                        person={person}
                                        className="border-b border-gray-100/70 px-6 py-3 last:border-0 dark:border-slate-800/50"
                                    />
                                ))
                            ) : (
                                <p className="px-6 py-3 text-xs text-gray-500 dark:text-gray-400">
                                    {/* A failed request is not an answer of
                                        "nobody" -- it must not borrow the
                                        wording that says nobody. */}
                                    {personAnswered
                                        ? personDetail || 'V našich dátach sme k tomuto menu nikoho nenašli.'
                                        : 'Zoznam osôb sa nepodarilo načítať.'}
                                </p>
                            )}

                            <div className="border-t border-gray-100 px-6 py-2.5 dark:border-slate-800/60">
                                <PersonCoverageNote coverage={personCoverage} />
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
