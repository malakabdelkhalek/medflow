param(
    [string]$SourceDir = (Join-Path $PSScriptRoot "..\sources"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\sources\clean")
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$pctPath = Join-Path $SourceDir "pct_human_medicines_raw.csv"
$rxnormPath = Join-Path $SourceDir "rxnorm_mapping.json"

if (-not (Test-Path $pctPath)) {
    throw "Missing PCT raw file: $pctPath"
}
if (-not (Test-Path $rxnormPath)) {
    throw "Missing RxNorm mapping file: $rxnormPath"
}

function Remove-Diacritics([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $normalized = $Value.Normalize([Text.NormalizationForm]::FormD)
    $builder = New-Object Text.StringBuilder
    foreach ($char in $normalized.ToCharArray()) {
        $category = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($char)
        if ($category -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
            [void]$builder.Append($char)
        }
    }
    return $builder.ToString().Normalize([Text.NormalizationForm]::FormC)
}

function Normalize-Token([string]$Value) {
    $ascii = Remove-Diacritics $Value
    $lower = $ascii.ToLowerInvariant()
    $clean = [regex]::Replace($lower, "[^a-z0-9]+", " ")
    return ([regex]::Replace($clean, "\s+", " ")).Trim()
}

function Test-TokenMatch([string]$Haystack, [string]$Needle) {
    if ([string]::IsNullOrWhiteSpace($Needle)) { return $false }
    $h = " $(Normalize-Token $Haystack) "
    $n = [regex]::Escape((Normalize-Token $Needle))
    return $h -match "(^| )$n( |$)"
}

$priorityDefinitions = @(
    @{ inn = "warfarin"; reason = "high-risk anticoagulant interactions" },
    @{ inn = "heparin"; reason = "high-risk anticoagulant interactions" },
    @{ inn = "aspirin"; reason = "antiplatelet bleeding risk" },
    @{ inn = "clopidogrel"; reason = "antiplatelet bleeding risk" },
    @{ inn = "metformin"; reason = "renal contraindication trap" },
    @{ inn = "glibenclamide"; reason = "hypoglycemia risk" },
    @{ inn = "insulin glargine"; reason = "hypoglycemia risk" },
    @{ inn = "enalapril"; reason = "ACE inhibitor renal/potassium risk" },
    @{ inn = "ramipril"; reason = "ACE inhibitor renal/potassium risk" },
    @{ inn = "amlodipine"; reason = "common cardiovascular drug" },
    @{ inn = "furosemide"; reason = "electrolyte/renal risk" },
    @{ inn = "spironolactone"; reason = "hyperkalemia risk" },
    @{ inn = "digoxin"; reason = "narrow therapeutic index" },
    @{ inn = "atorvastatin"; reason = "Tunisian brand duplication trap" },
    @{ inn = "simvastatin"; reason = "CYP3A4 inhibitor trap" },
    @{ inn = "ibuprofen"; reason = "NSAID bleeding/renal risk" },
    @{ inn = "diclofenac"; reason = "NSAID bleeding/renal risk" },
    @{ inn = "naproxen"; reason = "NSAID bleeding/renal risk" },
    @{ inn = "prednisolone"; reason = "steroid interaction risk" },
    @{ inn = "amoxicillin"; reason = "penicillin allergy trap" },
    @{ inn = "ciprofloxacin"; reason = "QT/CYP/renal concerns" },
    @{ inn = "metronidazole"; reason = "interaction-prone antimicrobial" },
    @{ inn = "clarithromycin"; reason = "strong CYP3A4 inhibitor trap" },
    @{ inn = "fluconazole"; reason = "CYP2C9 inhibitor trap" },
    @{ inn = "carbamazepine"; reason = "CYP inducer and neurologic risk" },
    @{ inn = "valproate"; reason = "neurologic and hepatic risk" },
    @{ inn = "fluoxetine"; reason = "serotonin syndrome trap" },
    @{ inn = "sertraline"; reason = "SSRI interaction risk" },
    @{ inn = "omeprazole"; reason = "common gastric/CYP interaction drug" },
    @{ inn = "tramadol"; reason = "serotonin syndrome trap" }
)

$aliasMap = @{
    "aspirin" = @("aspirin", "aspirine", "acide acetylsalicylique", "acetylsalicylate", "acetylsalicylate de lysine")
    "heparin" = @("heparin", "heparine", "enoxaparine", "nadroparine")
    "metformin" = @("metformin", "metformine")
    "glibenclamide" = @("glibenclamide", "glyburide")
    "insulin glargine" = @("insulin glargine", "insuline glargine", "glargine")
    "enalapril" = @("enalapril")
    "ramipril" = @("ramipril")
    "amlodipine" = @("amlodipine")
    "furosemide" = @("furosemide", "furosémide")
    "spironolactone" = @("spironolactone", "spironolactone")
    "digoxin" = @("digoxin", "digoxine")
    "atorvastatin" = @("atorvastatin", "atorvastatine")
    "simvastatin" = @("simvastatin", "simvastatine")
    "ibuprofen" = @("ibuprofen", "ibuprofene", "ibuprofène")
    "diclofenac" = @("diclofenac", "diclofenac", "diclofénac")
    "naproxen" = @("naproxen", "naproxene", "naproxène")
    "prednisolone" = @("prednisolone")
    "amoxicillin" = @("amoxicillin", "amoxicilline")
    "ciprofloxacin" = @("ciprofloxacin", "ciprofloxacine")
    "metronidazole" = @("metronidazole", "metronidazole", "métronidazole")
    "clarithromycin" = @("clarithromycin", "clarithromycine")
    "fluconazole" = @("fluconazole")
    "carbamazepine" = @("carbamazepine", "carbamazépine")
    "valproate" = @("valproate", "valproique", "acide valproique", "valproate de sodium")
    "fluoxetine" = @("fluoxetine", "fluoxétine")
    "sertraline" = @("sertraline")
    "omeprazole" = @("omeprazole", "oméprazole")
    "tramadol" = @("tramadol")
    "warfarin" = @("warfarin")
    "clopidogrel" = @("clopidogrel")
}

$brandSeedMap = @{
    "TAHOR" = "atorvastatin"
    "ATOR" = "atorvastatin"
    "LIPITOR" = "atorvastatin"
    "ZOCOR" = "simvastatin"
    "GLUCOPHAGE" = "metformin"
    "METFORAL" = "metformin"
    "DAONIL" = "glibenclamide"
    "LANTUS" = "insulin glargine"
    "KARDEGIC" = "aspirin"
    "ASPEGIC" = "aspirin"
    "ASPIRINE" = "aspirin"
    "PLAVIX" = "clopidogrel"
    "LASILIX" = "furosemide"
    "ALDACTONE" = "spironolactone"
    "LANOXIN" = "digoxin"
    "AMLOR" = "amlodipine"
    "NORVASC" = "amlodipine"
    "COVERSYL" = "perindopril"
    "TRIATEC" = "ramipril"
    "RENITEC" = "enalapril"
    "AUGMENTIN" = "amoxicillin"
    "AMOXIL" = "amoxicillin"
    "CIFLOX" = "ciprofloxacin"
    "FLAGYL" = "metronidazole"
    "ZECLAR" = "clarithromycin"
    "DIFLUCAN" = "fluconazole"
    "TEGRETOL" = "carbamazepine"
    "DEPAKINE" = "valproate"
    "PROZAC" = "fluoxetine"
    "ZOLOFT" = "sertraline"
    "MOPRAL" = "omeprazole"
    "TRAMAL" = "tramadol"
    "VOLTARENE" = "diclofenac"
    "BRUFEN" = "ibuprofen"
    "APRANAX" = "naproxen"
    "SOLUPRED" = "prednisolone"
}

$rxnormRows = Get-Content $rxnormPath -Raw | ConvertFrom-Json
$rxnormByInn = @{}
foreach ($row in $rxnormRows) {
    $rxnormByInn[$row.inn_name] = $row
}

$pctRows = Import-Csv $pctPath

$cleanBrandRows = New-Object System.Collections.Generic.List[object]
$unresolvedRows = New-Object System.Collections.Generic.List[object]
$matchCounts = @{}
foreach ($definition in $priorityDefinitions) {
    $matchCounts[$definition.inn] = 0
}

foreach ($row in $pctRows) {
    $fullLabel = $row.medicine_label
    $brandGuess = $row.brand_guess
    $brandToken = (Normalize-Token $brandGuess).ToUpperInvariant()
    $candidateInn = ""
    $confidence = ""
    $rule = ""

    if ($brandSeedMap.ContainsKey($brandToken)) {
        $seedInn = $brandSeedMap[$brandToken]
        if ($matchCounts.ContainsKey($seedInn)) {
            $candidateInn = $seedInn
            $confidence = "medium"
            $rule = "brand_seed"
        }
    }

    if (-not $candidateInn) {
        foreach ($definition in $priorityDefinitions) {
            $inn = $definition.inn
            foreach ($alias in $aliasMap[$inn]) {
                if (Test-TokenMatch $fullLabel $alias) {
                    $candidateInn = $inn
                    $confidence = "high"
                    $rule = "label_alias:$alias"
                    break
                }
            }
            if ($candidateInn) { break }
        }
    }

    if ($candidateInn) {
        $rx = $rxnormByInn[$candidateInn]
        $matchCounts[$candidateInn] += 1
        $cleanBrandRows.Add([pscustomobject]@{
            brand_name = $brandGuess
            full_label = $fullLabel
            strength = $row.strength_guess
            candidate_inn = $candidateInn
            rxnorm_cui = if ($rx) { $rx.rxnorm_cui } else { "" }
            confidence = $confidence
            match_rule = $rule
            source = "PCT"
            needs_manual_review = "false"
        })
    } else {
        $unresolvedRows.Add([pscustomobject]@{
            brand_name = $brandGuess
            full_label = $fullLabel
            strength = $row.strength_guess
            reason = "no_priority_inn_or_seed_match"
            source = "PCT"
            needs_manual_review = "true"
        })
    }
}

$moleculeRows = New-Object System.Collections.Generic.List[object]
$priorityRows = New-Object System.Collections.Generic.List[object]
$rxnormCleanRows = New-Object System.Collections.Generic.List[object]
$allergyGroupRows = New-Object System.Collections.Generic.List[object]
$drugAllergyRows = New-Object System.Collections.Generic.List[object]
$allergyCrossRows = New-Object System.Collections.Generic.List[object]

foreach ($definition in $priorityDefinitions) {
    $inn = $definition.inn
    $rx = $rxnormByInn[$inn]
    $rxnormCui = if ($rx) { $rx.rxnorm_cui } else { "" }
    $synonyms = if ($rx) { $rx.all_synonyms } else { "" }
    $pctCount = $matchCounts[$inn]

    $moleculeRows.Add([pscustomobject]@{
        canonical_inn = $inn
        rxnorm_cui = $rxnormCui
        rxnorm_synonyms = $synonyms
        pct_match_count = $pctCount
        source = "RxNorm + PCT"
        confidence = if ($rxnormCui) { "high" } else { "needs_review" }
        priority_phase = "week1_30"
    })

    $priorityRows.Add([pscustomobject]@{
        rank = $priorityRows.Count + 1
        canonical_inn = $inn
        rxnorm_cui = $rxnormCui
        pct_match_count = $pctCount
        selection_reason = $definition.reason
        selected_for_phase = "week1_30"
        needs_manual_review = if ($pctCount -eq 0) { "true" } else { "false" }
    })

    $rxnormCleanRows.Add([pscustomobject]@{
        canonical_inn = $inn
        rxnorm_cui = $rxnormCui
        rxnorm_synonyms = $synonyms
        status = if ($rx) { $rx.status } else { "missing" }
        source = "RxNorm"
    })
}

$allergyGroupDefinitions = @(
    @{
        name = "Penicillins"
        normalized_name = "penicillins"
        description = "Penicillin-class beta-lactam antibiotics; includes amoxicillin and related aminopenicillins."
        clinical_note = "Use for documented penicillin allergy, especially immediate hypersensitivity or anaphylaxis."
    },
    @{
        name = "Beta-lactams"
        normalized_name = "beta_lactams"
        description = "Broad beta-lactam antibiotic family including penicillins, cephalosporins, carbapenems, and monobactams."
        clinical_note = "Useful parent group for cross-reactivity review; do not treat all beta-lactam allergies as equal without reaction history."
    },
    @{
        name = "Cephalosporins"
        normalized_name = "cephalosporins"
        description = "Cephalosporin beta-lactam antibiotics."
        clinical_note = "Cross-reactivity risk is higher with similar side chains and severe immediate penicillin reactions."
    },
    @{
        name = "NSAIDs"
        normalized_name = "nsaids"
        description = "Non-steroidal anti-inflammatory drugs; includes ibuprofen, diclofenac, and naproxen."
        clinical_note = "Relevant for NSAID-exacerbated respiratory disease, urticaria/angioedema, and anaphylaxis."
    },
    @{
        name = "Salicylates"
        normalized_name = "salicylates"
        description = "Aspirin and salicylate-containing medicines."
        clinical_note = "Aspirin sensitivity can cross-react clinically with many COX-1 NSAIDs."
    },
    @{
        name = "Fluoroquinolones"
        normalized_name = "fluoroquinolones"
        description = "Fluoroquinolone antibiotics; includes ciprofloxacin."
        clinical_note = "Avoid same-class rechallenge after severe immediate hypersensitivity unless specialist-supervised."
    },
    @{
        name = "Macrolides"
        normalized_name = "macrolides"
        description = "Macrolide antibiotics; includes clarithromycin."
        clinical_note = "Allergy is less common but same-class alternatives require review when reaction was severe."
    },
    @{
        name = "Sulfonylureas"
        normalized_name = "sulfonylureas"
        description = "Sulfonylurea antidiabetics; includes glibenclamide."
        clinical_note = "Different from sulfonamide antibiotic allergy; keep distinct to avoid false positives."
    },
    @{
        name = "Insulins"
        normalized_name = "insulins"
        description = "Insulin preparations and analogues; includes insulin glargine."
        clinical_note = "Can involve insulin molecule or excipients; reaction details matter."
    },
    @{
        name = "Statins"
        normalized_name = "statins"
        description = "HMG-CoA reductase inhibitors; includes atorvastatin and simvastatin."
        clinical_note = "Distinguish allergy from intolerance such as myalgia."
    },
    @{
        name = "SSRIs"
        normalized_name = "ssris"
        description = "Selective serotonin reuptake inhibitors; includes fluoxetine and sertraline."
        clinical_note = "True allergy is uncommon; document rash, angioedema, or severe reactions separately from side effects."
    },
    @{
        name = "Opioids"
        normalized_name = "opioids"
        description = "Opioid analgesics and opioid-like medicines; includes tramadol."
        clinical_note = "Differentiate true allergy from histamine-mediated itching or nausea."
    }
)

foreach ($group in $allergyGroupDefinitions) {
    $allergyGroupRows.Add([pscustomobject]@{
        name = $group.name
        normalized_name = $group.normalized_name
        description = $group.description
        clinical_note = $group.clinical_note
        source = "MedFlow clinical seed"
        confidence = "starter_reviewed"
    })
}

$drugAllergyMap = @{
    "aspirin" = @("Salicylates", "NSAIDs")
    "ibuprofen" = @("NSAIDs")
    "diclofenac" = @("NSAIDs")
    "naproxen" = @("NSAIDs")
    "amoxicillin" = @("Penicillins", "Beta-lactams")
    "ciprofloxacin" = @("Fluoroquinolones")
    "clarithromycin" = @("Macrolides")
    "glibenclamide" = @("Sulfonylureas")
    "insulin glargine" = @("Insulins")
    "atorvastatin" = @("Statins")
    "simvastatin" = @("Statins")
    "fluoxetine" = @("SSRIs")
    "sertraline" = @("SSRIs")
    "tramadol" = @("Opioids")
}

foreach ($inn in $drugAllergyMap.Keys) {
    $rx = $rxnormByInn[$inn]
    foreach ($groupName in $drugAllergyMap[$inn]) {
        $drugAllergyRows.Add([pscustomobject]@{
            canonical_inn = $inn
            rxnorm_cui = if ($rx) { $rx.rxnorm_cui } else { "" }
            allergy_group = $groupName
            relationship_type = "member"
            clinical_note = "Alert when patient has documented allergy to this group and this molecule is prescribed."
            source = "MedFlow clinical seed"
            confidence = "starter_reviewed"
        })
    }
}

$crossDefinitions = @(
    @{
        group_a = "Penicillins"
        group_b = "Beta-lactams"
        direction = "bidirectional"
        clinical_note = "Penicillin allergy is part of the broader beta-lactam allergy review space."
        confidence = "high"
    },
    @{
        group_a = "Penicillins"
        group_b = "Cephalosporins"
        direction = "bidirectional"
        clinical_note = "Cross-reactivity is possible, especially with immediate severe reactions or similar side chains; requires pharmacist review."
        confidence = "moderate"
    },
    @{
        group_a = "Salicylates"
        group_b = "NSAIDs"
        direction = "bidirectional"
        clinical_note = "Aspirin/salicylate hypersensitivity can cross-react with non-selective NSAIDs."
        confidence = "high"
    }
)

foreach ($cross in $crossDefinitions) {
    $allergyCrossRows.Add([pscustomobject]@{
        group_a = $cross.group_a
        group_b = $cross.group_b
        direction = $cross.direction
        clinical_note = $cross.clinical_note
        source = "MedFlow clinical seed"
        confidence = $cross.confidence
    })
}

$cleanBrandRows |
    Sort-Object candidate_inn, brand_name, full_label |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "tunisian_brand_mapping_clean.csv")

$unresolvedRows |
    Sort-Object brand_name, full_label |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "unresolved_review_queue.csv")

$moleculeRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "molecules_candidates.csv")

$priorityRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "priority_drugs_30_60.csv")

$rxnormCleanRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "rxnorm_brand_mapping_clean.csv")

$allergyGroupRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "allergy_groups_clean.csv")

$drugAllergyRows |
    Sort-Object canonical_inn, allergy_group |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "drug_allergy_groups_clean.csv")

$allergyCrossRows |
    Export-Csv -NoTypeInformation -Encoding UTF8 -Path (Join-Path $OutputDir "allergy_cross_reactivities_clean.csv")

$summary = [pscustomobject]@{
    pct_raw_rows = $pctRows.Count
    matched_tunisian_brand_rows = $cleanBrandRows.Count
    unresolved_rows = $unresolvedRows.Count
    molecule_candidates = $moleculeRows.Count
    priority_drugs = $priorityRows.Count
    allergy_groups = $allergyGroupRows.Count
    drug_allergy_group_links = $drugAllergyRows.Count
    allergy_cross_reactivities = $allergyCrossRows.Count
    output_dir = (Resolve-Path $OutputDir).Path
}

$summary | ConvertTo-Json -Depth 3
