import streamlit as st
import pandas as pd
import io
import zipfile

# Configuração da página do Streamlit
st.set_page_config(page_title="Conversor de Laudos ArcGIS", layout="centered")

st.html(
    """
    <style>
    .stMainBlockContainer {
        max-width: 1000px;
    }
    </style>
    """
)

st.title("Conversor de Laudos -> ArcGIS ")
st.markdown("""
Este sistema processa os laudos de **Fertilidade** e **Sustentabilidade**, realiza os cruzamentos de dados 
e cria as abas do Modelo ArcGIS baseado nas profundidades encontradas no arquivo (ex: 00-20/20-40/40-60, 00-25/25-50, etc.).
""")

st.divider()

# --- INTERFACE DE UPLOAD ---
st.subheader("1. Selecione os Arquivos de Entrada")
col1, col2 = st.columns(2)

with col1:
    st.info("Laudo de Fertilidade")
    file_fert = st.file_uploader("Escolha o arquivo Fertilidade Completo", type=["xlsx"], key="fert")

with col2:
    st.success("Laudo de Sustentabilidade")
    file_sust = st.file_uploader("Escolha o arquivo de Sustentabilidade Completo", type=["xlsx"], key="sust")

# Função auxiliar para padronizar nomes de fazendas e evitar quebras de cruzamento
def normalizar_nome_fazenda(nome):
    if pd.isna(nome):
        return ""
    texto = str(nome).upper().strip()
    for termo in ["FAZENDA", "FAZ.", "SÍTIO", "SITIO", "CHÁCARA", "CHACARA"]:
        texto = texto.replace(termo, "")
    return texto.strip()

# --- ESTRUTURA DE COLUNAS PADRÃO DO SEU MODELO ARCGIS ---
COLUNAS_PROF_PADRAO = [
    "QR-Code", "Propriedade", "Nome_talhao", "N_ponto_talhao", "Longitude", "Latitude", 
    "Prof_inferior", "Prof_superior", "Carbono", "Argila", "pH_CaCl2", "pH_agua", 
    "P_resina", "P_mehlich", "S", "Mo", "Ca", "Mg", "K", "Al", "Ctc", "Sat_bases", 
    "Sat_Alum", "Hfil", "Ihmo", "Est_carb", "B", "Cu", "Fe", "Mn", "Zn", 
    "Calagem", "Gessagem", "Fosfatada", "Potassica"
]

COLUNAS_ESTOQUE_PADRAO = [
    "Propriedade", "Nome_talhao", "N_ponto_talhao", "Latitude", "Longitude", "Est_carb"
]

# --- PROCESSAMENTO DOS DADOS ---
if file_fert and file_sust:
    st.write("---")
    st.subheader("2. Executar Processamento")
    
    nome_original = file_fert.name
    try:
        cod_os = "".join(filter(str.isdigit, nome_original))[4:7]
        if not cod_os:
            cod_os = "999"
    except:
        cod_os = "999"
        
    st.warning(f"Código da OS identificado a partir do arquivo: **{cod_os}**")

    if st.button("Processar Planilhas", use_container_width=True):
        with st.spinner("Analisando profundidades e gerando estrutura dinâmica... Por favor, aguarde."):
            try:
                # 1. Leitura dos dados brutos
                fertilidade = pd.read_excel(file_fert, sheet_name=0)
                carbono_textura = pd.read_excel(file_sust, sheet_name=1)
                estoque_carbono = pd.read_excel(file_sust, sheet_name=2)

                # 2. Execução do Merge usando a chave primária única (QR-Code)
                merge = fertilidade.merge(
                    carbono_textura.drop(columns=['COORD_X', 'COORD_Y', 'FAZENDA', 'LABORATORIO', 'DATA_LAUDO', 'LAUDO', 'ID_TALHAO', 'ID_PONTO', 'PROFUNDIDADE']), 
                    on='ID_AMOSTRA (QRCod)', 
                    how='inner'
                )
                
                # Criamos a coluna normalizada DIRETAMENTE no resultado consolidado do merge
                merge['FAZENDA_NORM'] = merge['FAZENDA'].apply(normalizar_nome_fazenda)

                # Identificação das propriedades únicas consolidadas e mapeamento para o nome real
                propriedades_norm_unicas = merge['FAZENDA_NORM'].dropna().unique()
                mapa_nomes_reais = dict(zip(merge['FAZENDA_NORM'], merge['FAZENDA'].astype(str).str.strip()))

                # Identificação DINÂMICA de todas as profundidades reais contidas no laudo
                profundidades_encontradas = sorted([str(p).strip() for p in merge['PROFUNDIDADE'].dropna().unique()])
                st.info(f"Profundidades detectadas no laudo: {profundidades_encontradas}")

                # Preparação da base do Estoque de Carbono por índices
                # 0: COORD_X, 1: COORD_Y, 2: FAZENDA, 5: ID_TALHAO, 6: ID_PONTO, 7: Estoque
                estoque_base = estoque_carbono.iloc[:, [0, 1, 2, 5, 6, 7]].copy()
                estoque_base.columns = ['COORD_X', 'COORD_Y', 'FAZENDA', 'ID_TALHAO', 'ID_PONTO', 'Estoque de Carbono (ton/ha)']
                estoque_base['FAZENDA_NORM'] = estoque_base['FAZENDA'].apply(normalizar_nome_fazenda)

                # Dicionários de Mapeamento Técnico
                mapeamento_prof = {
                    'ID_AMOSTRA (QRCod)': 'QR-Code',
                    'FAZENDA': 'Propriedade',
                    'ID_TALHAO': 'Nome_talhao',
                    'ID_PONTO': 'N_ponto_talhao',
                    'COORD_X': 'Longitude',
                    'COORD_Y': 'Latitude',
                    'pH_CaCl2': 'pH_CaCl2',
                    'pH_agua': 'pH_agua',
                    'Ca_(cmolc/dm³)': 'Ca',
                    'Mg_(cmolc/dm³)': 'Mg',
                    'K_(mg/dm³)': 'K',
                    'Al_(cmolc/dm³)': 'Al',
                    'P_(res)_(mg/dm³)': 'P_resina',
                    'P_(meh)_(mg/dm³)': 'P_mehlich',
                    'S_(mg/dm³)': 'S',
                    'MOS_(g/dm³)': 'Mo',
                    'V_(%)': 'Sat_bases',
                    'Sat._Al_(%)': 'Sat_Alum',
                    'T_(cmolc/dm³)': 'Ctc',
                    'B_(mg/dm³)': 'B',
                    'Cu_(mg/dm³)': 'Cu',
                    'Fe_(mg/dm³)': 'Fe',
                    'Mn_(mg/dm³)': 'Mn',
                    'Zn_(mg/dm³)': 'Zn',
                    'Carbono\n(g kg-1)': 'Carbono',
                    'Argila\n(g kg-1)': 'Argila'
                }

                mapeamento_estoque = {
                    'FAZENDA': 'Propriedade',
                    'ID_TALHAO': 'Nome_talhao',
                    'COORD_X': 'Longitude',
                    'COORD_Y': 'Latitude',
                    'ID_PONTO': 'N_ponto_talhao',
                    'Estoque de Carbono (ton/ha)': 'Est_carb'
                }

                # --- GERAÇÃO DO ARQUIVO COMPLETO DINÂMICO ---
                buffer_completo = io.BytesIO()
                with pd.ExcelWriter(buffer_completo, engine='openpyxl') as writer:
                    
                    # Cria dinamicamente cada aba de profundidade encontrada
                    for prof in profundidades_encontradas:
                        df_prof = merge[merge['PROFUNDIDADE'] == prof].copy()
                        if not df_prof.empty:
                            partes_prof = prof.split('-')
                            df_prof['Prof_inferior'] = partes_prof[0] if len(partes_prof) > 0 else ""
                            df_prof['Prof_superior'] = partes_prof[1] if len(partes_prof) > 1 else ""
                            
                            df = df_prof.rename(columns=mapeamento_prof)
                            for col in COLUNAS_PROF_PADRAO:
                                if col not in df.columns:
                                    df[col] = ""
                            
                            df = df[COLUNAS_PROF_PADRAO].copy()
                            df.to_excel(writer, sheet_name=prof, startrow=0, index=False, header=True)
                    
                    # Cria a aba fixa de estoque de carbono
                    if not estoque_base.empty:
                        df_est = estoque_base.copy()
                        df_est = df_est.rename(columns=mapeamento_estoque)
                        for col in COLUNAS_ESTOQUE_PADRAO:
                            if col not in df_est.columns:
                                df_est[col] = ""
                        df_est = df_est[COLUNAS_ESTOQUE_PADRAO].copy()
                        df_est.to_excel(writer, sheet_name='estoque_carbono', startrow=0, index=False, header=True)

                buffer_completo.seek(0)

                # --- SEPARAÇÃO POR PROPRIEDADE E CONSTRUÇÃO DO ZIP ---
                st.info("Iniciando a divisão por propriedades...")
                buffer_zip = io.BytesIO()
                
                # Lista para registrar o resumo detalhado por profundidade
                dados_resumo = []

                with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
                    
                    for prop_norm in propriedades_norm_unicas:
                        nome_real = mapa_nomes_reais[prop_norm]
                        nome_prop_limpo = nome_real.replace(' ', '_').replace('/', '_')
                        nome_excel_prop = f"OS_{cod_os}_ArcGIS_{nome_prop_limpo}.xlsx"
                        
                        # Dicionário base do registro desta fazenda na tabela de resumo
                        registro_fazenda = {"Propriedade": nome_real}
                        
                        buffer_prop = io.BytesIO()
                        with pd.ExcelWriter(buffer_prop, engine='openpyxl') as writer_prop:
                            
                            # 1. Filtra as abas de profundidade dinâmicas para esta fazenda específica
                            for prof in profundidades_encontradas:
                                df_prof = merge[(merge['PROFUNDIDADE'] == prof) & (merge['FAZENDA_NORM'] == prop_norm)].copy()
                                
                                # Guarda a quantidade exata de pontos para esta profundidade específica
                                registro_fazenda[f"Amostras ({prof})"] = len(df_prof)
                                
                                if not df_prof.empty:
                                    partes_prof = prof.split('-')
                                    df_prof['Prof_inferior'] = partes_prof[0] if len(partes_prof) > 0 else ""
                                    df_prof['Prof_superior'] = partes_prof[1] if len(partes_prof) > 1 else ""
                                    
                                    df = df_prof.rename(columns=mapeamento_prof)
                                    for col in COLUNAS_PROF_PADRAO:
                                        if col not in df.columns:
                                            df[col] = ""
                                    
                                    df = df[COLUNAS_PROF_PADRAO].copy()
                                    df.to_excel(writer_prop, sheet_name=prof, startrow=0, index=False, header=True)
                            
                            # 2. Filtra a aba de estoque de carbono para esta fazenda específica
                            df_est_prop = estoque_base[estoque_base['FAZENDA_NORM'] == prop_norm].copy()
                            
                            # Guarda a quantidade de pontos do estoque de carbono
                            registro_fazenda["Estoque Carbono"] = len(df_est_prop)
                            
                            if not df_est_prop.empty:
                                df_est_prop = df_est_prop.rename(columns=mapeamento_estoque)
                                for col in COLUNAS_ESTOQUE_PADRAO:
                                    if col not in df_est_prop.columns:
                                        df_est_prop[col] = ""
                                df_est_prop = df_est_prop[COLUNAS_ESTOQUE_PADRAO].copy()
                                df_est_prop.to_excel(writer_prop, sheet_name='estoque_carbono', startrow=0, index=False, header=True)
                        
                        # Adiciona o registro estruturado da fazenda na lista
                        dados_resumo.append(registro_fazenda)
                        
                        buffer_prop.seek(0)
                        arquivo_zip.writestr(nome_excel_prop, buffer_prop.read())

                buffer_zip.seek(0)

                # Salva os estados na sessão do Streamlit
                st.session_state["download_completo"] = buffer_completo.getvalue()
                st.session_state["download_zip"] = buffer_zip.getvalue()
                st.session_state["nome_completo"] = f"OS_{cod_os}_ArcGIS_Completo.xlsx"
                st.session_state["nome_zip"] = f"OS_{cod_os}_ArcGIS_Separado.zip"
                
                # Salva o DataFrame final de resumo estruturado na sessão
                st.session_state["df_resumo_fazendas"] = pd.DataFrame(dados_resumo)
                
                st.success("Processamento dinâmico concluído com sucesso!")

            except Exception as e:
                st.error(f"Erro durante o processamento: {e}")

# --- SEÇÃO DE DOWNLOADS E RESUMOS ---
if "download_completo" in st.session_state:
    st.write("---")
    
    # Renderiza a tabela dinâmica detalhando por profundidade
    if "df_resumo_fazendas" in st.session_state:
        st.subheader("2. Resumo de Pontos por Profundidade")
        st.markdown("Obs: pontos adicionais em 'Estoque Carbono' se referem aos pontos de Mata")
        st.dataframe(
            st.session_state["df_resumo_fazendas"], 
            use_container_width=True, 
            hide_index=True
        )
        st.write("")
    
    st.divider()

    st.subheader("3. Baixar Resultados")
    
    col_down1, col_down2 = st.columns(2)
    
    with col_down1:
        st.download_button(
            label="Baixar Arquivo Completo (.xlsx)",
            data=st.session_state["download_completo"],
            file_name=st.session_state["nome_completo"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with col_down2:
        st.download_button(
            label="Baixar Arquivos Separados por Fazenda (.zip)",
            data=st.session_state["download_zip"],
            file_name=st.session_state["nome_zip"],
            mime="application/zip",
            use_container_width=True
        )