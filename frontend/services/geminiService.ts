
import { GoogleGenAI } from "@google/genai";
import type { Company } from '../types';

// Calls the Gemini API to generate a risk summary for a company.
export const generateRiskSummary = async (companyData: Company): Promise<string> => {
    try {
        // FIX: As per guidelines, assume API_KEY is available and initialize the client.
        const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

        const simplifiedData = {
            name: companyData.name,
            status: companyData.status,
            debts: companyData.debts,
            vat_status: companyData.vatStatus,
            risk_score: companyData.riskScore,
            connections_count: companyData.connections.length,
            risky_connections: companyData.connections.filter(c => c.status !== 'Aktívna'),
            financials: companyData.financials
        };

        const prompt = `
            Si finančný analytik so špecializáciou na risk management. Tvojou úlohou je analyzovať priložené dáta o slovenskej firme a vytvoriť profesionálny report v Markdown formáte.

            Údaje o firme:
            ${JSON.stringify(simplifiedData)}

            Požiadavky na formátovanie:
            1. Použi nadpis H2 (##) pre hlavný verdikt (napr. "## Verdikt: Stredné Riziko").
            2. Použi Markdown tabuľku pre zobrazenie finančnej histórie (Rok | Tržby | Zisk) a pre zoznam dlhov (Zdroj | Suma).
            3. Použi odrážky pre kľúčové rizikové faktory.
            4. Text musí byť v slovenčine, profesionálny a stručný.
            5. Ak má firma dlhy alebo je v likvidácii, zvýrazni to tučným písmom (**text**).
            
            Štruktúra reportu:
            - Verdikt (jedna veta)
            - Kľúčové riziká (zoznam)
            - Finančný prehľad (tabuľka)
            - Analýza prepojení (ak sú rizikové)
        `;

        const response = await ai.models.generateContent({
            model: 'gemini-3-flash-preview',
            contents: prompt,
        });

        // FIX: The response.text property can be undefined. Provide a fallback string to satisfy the function's Promise<string> return type.
        return response.text ?? "AI neposkytla zhrnutie.";
    } catch (error) {
        console.error("Error calling Gemini API:", error);
        return "Nastala chyba pri generovaní AI zhrnutia. Skúste to prosím neskôr.";
    }
};
