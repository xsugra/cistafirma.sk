/**
 * The company page's section registry.
 *
 * One owner for the list, because three things have to agree on it: the
 * navigation rail, the route (`/firma/:ico/:sekcia`) and the section bodies. A
 * section in the rail but not in the route is a dead link; one in the route but
 * not in the rail is a page nobody can reach.
 *
 * `status` is not decoration. FinStat's rail lists eighteen entries because it
 * has eighteen things to show. Ours lists twenty and says plainly which of them
 * we cannot fill — a list that hides what it lacks reads as a list that has
 * everything, which is the one thing it must not do.
 */

export type SectionStatus =
    /** We have the data and render it. Every one of these has a body. */
    | 'ready'
    /** We have part of it; the section says which part. */
    | 'partial'
    /** We have it and it is wrong. We say so instead of drawing it. */
    | 'unreliable'
    /** The source is free; nobody has built the integration yet. */
    | 'planned'
    /** The source only exists behind a paid service. */
    | 'paid';

export type SectionGroup = 'Firma' | 'Financie' | 'Riziká a súdy' | 'Ľudia a väzby' | 'Databáza';

export interface CompanySection {
    id: string;
    label: string;
    icon: string;
    group: SectionGroup;
    status: SectionStatus;
    /** The reason, in the reader's words. Shown in place of a body. */
    note: string;
}

export const SECTION_GROUPS: readonly SectionGroup[] = [
    'Firma', 'Financie', 'Riziká a súdy', 'Ľudia a väzby', 'Databáza',
];

export const COMPANY_SECTIONS = [
    {
        id: 'prehlad', label: 'Prehľad o firme', icon: 'fa-chart-pie', group: 'Firma', status: 'ready',
        note: 'Základné údaje, hospodárske výsledky a kapitál spoločnosti.',
    },
    {
        id: 'skore', label: 'Rizikové skóre', icon: 'fa-tachometer-alt', group: 'Firma', status: 'ready',
        note: 'Skóre a rozpad na faktory, z ktorých vzniká — nedoplatky, Altmanova zóna a rentabilita aktív. Je to naše vlastné skóre z verejných dát, nie cudzí model.',
    },
    {
        id: 'register', label: 'Obchodný register', icon: 'fa-landmark', group: 'Firma', status: 'ready',
        note: 'Zápis v ORSR: predmet činnosti, oddiel, vložka, konanie menom spoločnosti.',
    },

    {
        id: 'report', label: 'Finančný report', icon: 'fa-file-pdf', group: 'Financie', status: 'ready',
        note: 'Zhrnutie firmy na stiahnutie.',
    },
    {
        id: 'ukazovatele', label: 'Finančné ukazovatele', icon: 'fa-calculator', group: 'Financie', status: 'ready',
        note: 'Ukazovatele a medziročné porovnanie.',
    },
    {
        id: 'suvaha', label: 'Súvaha', icon: 'fa-balance-scale', group: 'Financie', status: 'ready',
        note: 'Aktíva a pasíva po rokoch, s kontrolou, že aktíva = vlastné imanie + záväzky + časové rozlíšenie. Chýbajúce časové rozlíšenie čítame ako nulu — v 2 326 z 2 336 takých riadkov to tak naozaj je. Kontrola sedí presne v 13 816 zo 14 652 riadkov (94,3 %); keď závierke chýba iné číslo, kontrola to pomenuje a rovnicu neposudzuje.',
    },
    {
        id: 'vykaz', label: 'Výkaz ziskov a strát', icon: 'fa-chart-line', group: 'Financie', status: 'ready',
        note: 'Tržby, náklady, pridaná hodnota, dane a výsledok hospodárenia po rokoch, s medziročnou zmenou.',
    },
    {
        id: 'zaverky', label: 'Účtovné závierky', icon: 'fa-file-invoice', group: 'Financie', status: 'ready',
        note: 'Koľko závierok pre firmu eviduje RUZ a koľko z nich sme prečítali, s odkazom na portál RUZ. Prílohy — správa audítora, výročná správa, PDF — sa do databázy nesťahujú; na ne je odkaz, nie sťahovanie.',
    },

    {
        id: 'dlhy', label: 'Dlhy a pohľadávky', icon: 'fa-hand-holding-usd', group: 'Riziká a súdy', status: 'ready',
        note: 'Zoznamy dlžníkov Finančnej správy, VšZP a Sociálnej poisťovne.',
    },
    {
        id: 'udalosti', label: 'Udalosti vo firme', icon: 'fa-bell', group: 'Riziká a súdy', status: 'ready',
        note: 'Zatiaľ tri typy udalostí — zmena dlhu, zmena statusu a zmena štatutára — a len pre prihláseného: sú to notifikácie, ktoré sme poslali tebe o tejto firme, nie história firmy. Môžu existovať len pre firmy v tvojich sledovaných a vznikajú až od chvíle, keď si firmu pridal. Plná verzia by bola agregácia cez šesť zdrojov a je to najťažšia položka zoznamu.',
    },
    {
        id: 'platobne-rozkazy', label: 'Platobné rozkazy', icon: 'fa-file-signature', group: 'Riziká a súdy', status: 'planned',
        note: 'Sú v otvorených dátach, ale bez príznaku „toto je platobný rozkaz" — pomiešané v prúde súdnych rozhodnutí. Nebola by to integrácia, ale klasifikácia textu.',
    },
    {
        id: 'sudne-rozhodnutia', label: 'Súdne rozhodnutia', icon: 'fa-gavel', group: 'Riziká a súdy', status: 'planned',
        note: 'Otvorené dáta na obcan.justice.sk, licencia CC BY-SA 4.0. Bez API, najväčší súbor má ~7,6 GB a čerstvosť je nerovnomerná.',
    },
    {
        id: 'exekucie', label: 'Exekúcie', icon: 'fa-user-slash', group: 'Riziká a súdy', status: 'paid',
        note: 'Bezplatný register MS SR pokrýva len exekúcie po 1. 4. 2017 a len ručným vyhľadaním. Strojová cesta je platená (CRE, 1,60 € za prístup) — a exekúcie spred roku 2017 sú výhradne tam.',
    },

    {
        id: 'osoby', label: 'Osoby', icon: 'fa-users', group: 'Ľudia a väzby', status: 'ready',
        note: 'Štatutárne orgány, spoločníci, akcionári a prokúra.',
    },
    {
        id: 'prepojenia', label: 'Prepojenia', icon: 'fa-project-diagram', group: 'Ľudia a väzby', status: 'ready',
        note: 'Graf osoba — firma naprieč celou databázou.',
    },

    {
        id: 'podobne', label: 'Podobné spoločnosti', icon: 'fa-clone', group: 'Databáza', status: 'ready',
        note: 'Firmy v tej istej divízii SK NACE, zoradené podľa toho, ako blízko je ich obrat k obratu tejto firmy. Blízkosť sa počíta v pomere — firma s dvojnásobným obratom je bližšie než firma s desaťnásobným, hoci v eurách môže byť ďalej.',
    },
    {
        id: 'databaza-kraj', label: 'Firmy v kraji', icon: 'fa-map-marker-alt', group: 'Databáza', status: 'ready',
        note: 'Najväčšie firmy v kraji sídla tejto firmy. Sekcia vždy vypíše, koľko firiem v kraji máme a koľko z nich má zverejnenú závierku s tržbami — bez toho druhého čísla by sa „najväčšie v kraji" dalo čítať ako „zo všetkých firiem v kraji".',
    },
    {
        id: 'databaza-odvetvie', label: 'Firmy v odvetví', icon: 'fa-industry', group: 'Databáza', status: 'ready',
        note: 'Najväčšie firmy v tej istej divízii SK NACE, teda podľa prvého dvojčíslia kódu.',
    },
    {
        id: 'databaza-zamestnanci', label: 'Firmy podľa zamestnancov', icon: 'fa-user-friends', group: 'Databáza', status: 'planned',
        note: 'Číselný počet zamestnancov nemáme. V registri je len kód pásma, a to „00" má vyše 70 % firiem, takže ide o nevyplnené pole a nie o kategóriu. Nikde v projekte neexistuje mapovanie kódu na pásmo — admin filter ponúka „mikro/small/medium/large", čo nezodpovedá žiadnej hodnote v dátach — takže nemáme ani ako zistiť, čo tie kódy znamenajú. Najprv musí existovať to mapovanie.',
    },
    {
        id: 'databaza-trzby', label: 'Firmy podľa tržieb', icon: 'fa-coins', group: 'Databáza', status: 'ready',
        note: 'Najväčšie firmy v celom registri podľa poslednej zverejnenej závierky. Aj tu sekcia vypíše, koľko aktívnych firiem register má a koľko z nich vôbec zverejnilo tržby — je to zlomok registra a bez toho čísla by rebríček vyzeral ako rebríček všetkých.',
    },
] as const satisfies readonly CompanySection[];

export type CompanySectionId = typeof COMPANY_SECTIONS[number]['id'];

/** Sections that render a real body. The body map is typed against this, so a
 * section marked `ready` without one fails the typecheck rather than silently
 * showing an empty page. */
export type ReadySectionId = Extract<typeof COMPANY_SECTIONS[number], { status: 'ready' }>['id'];

export const DEFAULT_SECTION_ID: CompanySectionId = 'prehlad';

export const getSection = (id: string | undefined): CompanySection | undefined =>
    id ? COMPANY_SECTIONS.find((s) => s.id === id) : undefined;

/** Rail dots. Colour carries the same meaning as the chip in the section body —
 * the rail is how a reader finds out what is missing before clicking. */
export const STATUS_DOT: Record<SectionStatus, string> = {
    ready: 'bg-green-500',
    partial: 'bg-amber-500',
    unreliable: 'bg-red-500',
    planned: 'bg-slate-400 dark:bg-slate-500',
    paid: 'bg-purple-500',
};

/** No section is marked `unreliable` today, and that is a judgement rather than
 * an oversight: it means "we have the data and it is bad", which is a different
 * claim from `partial` ("we have some of it"). Nothing currently earns it --
 * each source either reads cleanly or is refused at the parser. The status is
 * kept because the alternative, when a source does start lying, is to notice it
 * and have nowhere to say so. */
export const STATUS_LABEL: Record<SectionStatus, string> = {
    ready: 'Máme dáta',
    partial: 'Máme časť',
    unreliable: 'Údaje sú nespoľahlivé',
    planned: 'Zatiaľ nemáme',
    paid: 'Len za peniaze',
};

export const STATUS_CHIP: Record<SectionStatus, string> = {
    ready: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800',
    partial: 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    unreliable: 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800',
    planned: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    paid: 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-800',
};
