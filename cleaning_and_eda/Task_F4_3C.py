import pandas as pd

# 1. Chargement des données
print("1. Chargement du fichier CSV...")
df = pd.read_csv('cedint_f1_hourly.csv (1)/cedint_f1_hourly.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
# Nettoyage des valeurs négatives et remplissage de l'énergie manquante
df['power_w'] = df['power_w'].clip(lower=0)
df['energy_wh'] = df['energy_wh'].fillna(df['power_w'])

# 2. Extraction des colonnes temporelles
print("2. Extraction des caractéristiques calendaires...")
df['year'] = df['timestamp'].dt.year
df['month'] = df['timestamp'].dt.month
df['dayofweek'] = df['timestamp'].dt.dayofweek
df['date_str'] = df['timestamp'].dt.strftime('%Y-%m-%d')

# Liste des jours fériés à Madrid (2020-2025)
spanish_holidays = [
    '2020-01-01', '2020-01-06', '2020-04-09', '2020-04-10', '2020-05-01', '2020-05-02', '2020-08-15', '2020-10-12', '2020-11-01', '2020-12-06', '2020-12-08', '2020-12-25',
    '2021-01-01', '2021-01-06', '2021-04-01', '2021-04-02', '2021-05-01', '2021-05-03', '2021-10-12', '2021-11-01', '2021-12-06', '2021-12-08', '2021-12-25',
    '2022-01-01', '2022-01-06', '2022-04-14', '2022-04-15', '2022-05-02', '2022-07-25', '2022-08-15', '2022-10-12', '2022-11-01', '2022-12-06', '2022-12-08', '2022-12-26',
    '2023-01-01', '2023-01-06', '2023-04-06', '2023-04-07', '2023-05-01', '2023-05-02', '2023-07-25', '2023-08-15', '2023-10-12', '2023-11-01', '2023-12-06', '2023-12-08', '2023-12-25',
    '2024-01-01', '2024-01-06', '2024-03-28', '2024-03-29', '2024-05-01', '2024-05-02', '2024-07-25', '2024-08-15', '2024-10-12', '2024-11-01', '2024-12-06', '2024-12-08', '2024-12-25',
    '2025-01-01', '2025-01-06', '2025-04-17', '2025-04-18', '2025-05-01', '2025-05-02', '2025-07-25', '2025-08-15', '2025-10-12', '2025-11-01', '2025-12-06', '2025-12-08', '2025-12-25'
]

# 3. Création des étiquettes (Flags explicatifs)
print("3. Création des flags explicatifs...")
df['is_weekend'] = df['dayofweek'].isin([5, 6])
df['is_holiday'] = df['date_str'].isin(spanish_holidays)
df['is_august'] = df['month'] == 8
df['is_low_use_expected'] = df['is_weekend'] | df['is_holiday'] | df['is_august']

def identifier_categorie(row):
    if row['is_august']:
        return "Mois d'Août (Fermeture estivale)"
    elif row['is_holiday']:
        return "Jour Férié"
    elif row['is_weekend']:
        return "Week-end"
    else:
        return "Jour Ouvré Normal"

df['day_category'] = df.apply(identifier_categorie, axis=1)

# 4. Affichage du résumé et sauvegarde
print("\n--- RÉSULTATS DE L'ANALYSE ---")
resume = df.groupby('day_category')['energy_wh'].agg(['count', 'mean']).reset_index()
resume.columns = ['Catégorie de jour', 'Nombre d\'heures', 'Consommation Moyenne (Wh)']
print(resume)

df.to_csv('cedint_f1_hourly_F4.3C.csv', index=False)
print("\nFichier généré avec succès : 'cedint_f1_hourly_F4.3C.csv'")