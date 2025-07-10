import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from babel.numbers import (
    format_currency,
)  # <-- coloca isso antes de usar format_currency
import plotly.express as px
from datetime import datetime, date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import time
from plyer import notification
import plotly.graph_objects as go
from pathlib import Path
import logging
from tqdm import tqdm
import json

# ==================== SISTEMA DE AUTENTICAÇÃO ====================

def verificar_login():
    """Verifica se o usuário está logado"""
    return st.session_state.get('logado', False)

def fazer_login(usuario, senha):
    """Valida credenciais e autentica o usuário"""
    if usuario == "admin" and senha == "Acesso@2025":
        st.session_state['logado'] = True
        st.session_state['usuario'] = usuario
        return True
    return False

def fazer_logout():
    """Realiza logout do usuário"""
    st.session_state['logado'] = False
    st.session_state['usuario'] = None
    st.rerun()

def tela_login():
    """Exibe a tela de login"""
    # Configuração da página para login
    st.set_page_config(page_title="Login - Logística Assa Abloy", page_icon="🔐", layout="centered")
    
    # Centralizar o conteúdo
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 2rem 0;'>
            <h1>🔐 Login Dashboard</h1>
            <h3>Logística Assa Abloy</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Formulário de login
        with st.form("login_form"):
            st.markdown("### Acesso ao Sistema")
            
            usuario = st.text_input("👤 Usuário", placeholder="Digite seu usuário")
            senha = st.text_input("🔒 Senha", type="password", placeholder="Digite sua senha")
            
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
            with col_btn2:
                submit_button = st.form_submit_button("🚀 Entrar", use_container_width=True)
            
            if submit_button:
                if not usuario or not senha:
                    st.error("❌ Por favor, preencha todos os campos!")
                elif fazer_login(usuario, senha):
                    st.success("✅ Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos!")
        
        # Informações adicionais
        st.markdown("""
        <div style='text-align: center; margin-top: 2rem; padding: 1rem; background-color: #f0f2f6; border-radius: 10px;'>
            <small>
                <strong>Dashboard de Logística</strong><br>
                Sistema de acompanhamento de faturamento e devoluções<br>
                <em>Versão 2025</em>
            </small>
        </div>
        """, unsafe_allow_html=True)

# ==================== VERIFICAÇÃO DE AUTENTICAÇÃO ====================

# Inicializar session state
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Verificar se o usuário está logado
if not verificar_login():
    tela_login()
    st.stop()

# 🎯 Configuração inicial da página (após login)
st.set_page_config(page_title="Logística Assa Abloy", page_icon="🎯", layout="wide")

# Header com informações do usuário e logout
col_header1, col_header2 = st.columns([3, 1])

with col_header1:
    st.title("📈 Dashboard CD - 2025")

with col_header2:
    st.markdown(f"""
    <div style='text-align: right; margin-top: 1rem;'>
        <small>Usuário: <strong>{st.session_state.get('usuario', 'admin')}</strong></small>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 Logout", type="secondary", use_container_width=True):
        fazer_logout()

# ==================== FUNÇÕES DE TRATAMENTO DE DADOS ====================

def tentar_converter_datas(df, colunas_data):
    """Converte colunas de data para datetime com múltiplos formatos"""
    formatos_teste = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]
    for col in colunas_data:
        convertido = False
        for fmt in formatos_teste:
            try:
                temp = pd.to_datetime(df[col], format=fmt, errors="coerce")
                if temp.notna().sum() > 0:
                    df[col] = temp
                    convertido = True
                    break
            except Exception:
                continue
        if not convertido:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

def preencher_domino(df, destino, fontes):
    """Preenche valores nulos em cascata"""
    for fonte in fontes:
        if fonte in df.columns:
            df[destino] = df[destino].combine_first(df[fonte])
    return df

def processar_dados_upload(df):
    """Aplica todos os tratamentos necessários nos dados"""
    
    # Normalizar nomes das colunas
    df.columns = (
        df.columns.str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "", regex=False)
    )
    
    # Converter série para string
    if "serie" in df.columns:
        df["serie"] = df["serie"].astype(str).str.strip()
    
    # Converter datas
    colunas_datas = [
        "dt_implant_ped",
        "dt_embarque", 
        "dt_aprov_credito",
        "dt_emis_nf",
        "dt_entrega",
    ]
    colunas_presentes = [col for col in colunas_datas if col in df.columns]
    tentar_converter_datas(df, colunas_presentes)
    
    # Preenchimento em cascata das datas
    if set(["dt_aprov_credito", "dt_implant_ped"]).issubset(df.columns):
        preencher_domino(df, "dt_aprov_credito", ["dt_implant_ped"])
    
    if set(["dt_entrega", "dt_aprov_credito", "dt_implant_ped"]).intersection(df.columns):
        preencher_domino(df, "dt_entrega", ["dt_aprov_credito", "dt_implant_ped"])
    
    if set(["dt_emis_nf", "dt_embarque"]).issubset(df.columns):
        preencher_domino(df, "dt_emis_nf", ["dt_embarque"])
    
    # Preencher valores nulos
    df.fillna({
        "canal_venda_cliente": "Desconhecido",
        "ped_cliente": "Sem Pedido", 
        "deposito": "Não Informado",
        "nro_embarque": "Sem Embarque",
    }, inplace=True)
    
    # Converter receita para boolean
    if "receita" in df.columns:
        df["receita"] = (
            df["receita"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"sim": True, "não": False})
            .astype(bool)
        )
    
    # Converter valores numéricos
    for col in ["vl_net_livro", "quantidade"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace("[^0-9.-]", "", regex=True)
                .astype(float)
                .abs()
            )
    
    # Limpar marcas
    if "marca" in df.columns:
        indesejadas = {"?", "METALIKA", "MTK CD SP", "PAPAIZ SOR", "YALE"}
        df = df[~df["marca"].isin(indesejadas)]
        df["marca"] = df["marca"].replace("SILVANA CDSP", "SILVANA")
    
    return df

# ==================== SEÇÃO DE UPLOAD ====================

st.sidebar.header("📁 Atualização de Dados")

uploaded_file = st.sidebar.file_uploader(
    "Faça upload do arquivo ESFT0100.csv",
    type=['csv'],
    help="Selecione o arquivo CSV para atualizar os dados do dashboard"
)

# Verificar se existe arquivo atual
arquivo_parquet = Path("Datasets/ESFT/ESFT0100_atual.parquet")
dados_carregados = False

if uploaded_file is not None:
    try:
        with st.sidebar:
            st.info("🔄 Processando arquivo...")
            
            # Definir colunas esperadas
            colunas_fat = [
                "Cod Estab", "Razao Social", "Cidade", "Estado", "Canal Venda Cliente",
                "Dt Implant Ped", "Ped Cliente", "Ped Datasul", "Tipo Oper", "Serie",
                "Nota Fiscal", "Natureza", "Dt Emis NF", "Dt Embarque", "Dt Aprov. Credito",
                "Receita", "Item", "Desc Item", "Deposito", "Quantidade", "Vl Net Livro",
                "Nro Embarque", "Marca", "Dt Entrega", "Situacao Ped"
            ]
            
            # Ler arquivo
            df_novo = pd.read_csv(
                uploaded_file,
                sep=";",
                encoding="ISO-8859-1", 
                quotechar='"',
                low_memory=False
            )
            
            # Verificar colunas disponíveis
            colunas_disponiveis = df_novo.columns.tolist()
            colunas_validas = [col for col in colunas_fat if col in colunas_disponiveis]
            
            if colunas_validas:
                df_novo = df_novo[colunas_validas]
                
                # Aplicar tratamentos
                df_processado = processar_dados_upload(df_novo)
                
                # Salvar arquivo processado
                os.makedirs("Datasets/ESFT", exist_ok=True)
                df_processado.to_parquet(arquivo_parquet, index=False)
                
                st.success("✅ Dados processados e salvos com sucesso!")
                st.info(f"📊 {len(df_processado)} registros processados")
                
                # Mostrar informações do arquivo
                if "dt_emis_nf" in df_processado.columns:
                    ultima_data = df_processado["dt_emis_nf"].dropna().max()
                    if pd.notna(ultima_data):
                        st.info(f"📅 Última data: {ultima_data.strftime('%d/%m/%Y')}")
                
                dados_carregados = True
                
            else:
                st.error("❌ Nenhuma coluna válida encontrada no arquivo!")
                
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo: {str(e)}")

# ==================== CARREGAMENTO DE DADOS ====================

@st.cache_data
def carregar_faturamento():
    if arquivo_parquet.exists():
        return pd.read_parquet(arquivo_parquet)
    else:
        st.warning("⚠️ Nenhum arquivo de dados encontrado. Faça upload de um arquivo CSV.")
        return pd.DataFrame()

# Só carrega os dados se existir o arquivo ou se foi feito upload
if arquivo_parquet.exists() or dados_carregados:
    df_faturamento = carregar_faturamento()
    
    if df_faturamento.empty:
        st.stop()
        
else:
    st.warning("📁 **Nenhum dado disponível**")
    st.info("👆 Faça upload de um arquivo CSV na barra lateral para começar")
    st.stop()

# ==================== RESTO DO CÓDIGO ORIGINAL ====================

df_devolucao = df_faturamento.copy()  # usa o mesmo arquivo inicialmente

# ==================== GERENCIAMENTO DO CUTOFF (SIMILAR ÀS METAS) ====================

def carregar_cutoff_editavel():
    """Carrega cutoff editável do arquivo JSON local"""
    cutoff_file = "cutoff_marcas.json"
    
    # Cutoff padrão caso o arquivo não exista
    cutoff_padrao = {
        "LA FONTE": {"cutoff_inicial": 0.0, "cutoff_final": 0.0},
        "PAPAIZ": {"cutoff_inicial": 0.0, "cutoff_final": 0.0},
        "SILVANA": {"cutoff_inicial": 0.0, "cutoff_final": 0.0},
        "VAULT": {"cutoff_inicial": 0.0, "cutoff_final": 0.0}
    }
    
    try:
        if os.path.exists(cutoff_file):
            with open(cutoff_file, 'r', encoding='utf-8') as f:
                cutoff = json.load(f)
            return cutoff
        else:
            # Criar arquivo com cutoff padrão
            salvar_cutoff_editavel(cutoff_padrao)
            return cutoff_padrao
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar cutoff editável: {e}")
        return cutoff_padrao

def salvar_cutoff_editavel(cutoff_dict):
    """Salva cutoff editável no arquivo JSON local"""
    cutoff_file = "cutoff_marcas.json"
    
    try:
        with open(cutoff_file, 'w', encoding='utf-8') as f:
            json.dump(cutoff_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar cutoff: {e}")
        return False

# Carregar cutoff editável
cutoff_dados = carregar_cutoff_editavel()
cutoff_disponivel = True


# 🔨 Tratamentos nos DataFrames
operacoes_faturamento = [
    "1 - Receita",
    "20 - Receita Revenda",
    "2 - Receita Export",
    "3 - Receita Rem Vend Futura",
    "18 - Venda a ordem",
]

# Faturamento
df_faturamento = df_faturamento[df_faturamento["tipo_oper"].isin(operacoes_faturamento)]

# Devolução
df_devolucao = df_devolucao[df_devolucao["tipo_oper"] == "5 - Dev Venda"]
df_devolucao = df_devolucao[df_devolucao["marca"] != "YALE"]

# 🎯 Limpeza de Marcas
marcas_excluidas = ["PORTO FELIZ", "METALIKA", "YALE"]

# Normalize o nome das marcas para upper case
df_faturamento["marca"] = df_faturamento["marca"].str.upper()
df_devolucao["marca"] = df_devolucao["marca"].str.upper()

# Remover marcas indesejadas
df_faturamento = df_faturamento[~df_faturamento["marca"].isin(marcas_excluidas)]
df_devolucao = df_devolucao[~df_devolucao["marca"].isin(marcas_excluidas)]

# ==================== FUNÇÃO AUXILIAR PARA FORMATAÇÃO SEGURA ====================
def formatar_valor_seguro(valor, formato="currency"):
    """Formata valores de forma segura, tratando None e NaN"""
    if pd.isna(valor) or valor is None:
        return "R$ 0,00" if formato == "currency" else "0"
    
    try:
        if formato == "currency":
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif formato == "decimal":
            return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif formato == "integer":
            return f"{int(float(valor)):,}".replace(",", ".")
        else:
            return str(valor)
    except (ValueError, TypeError):
        return "R$ 0,00" if formato == "currency" else "0"

# 📅 Configuração de Datas
st.sidebar.subheader("📅 Selecione um Período para Análise")

# Garantir formato datetime nas datas
df_faturamento["dt_emis_nf"] = pd.to_datetime(
    df_faturamento["dt_emis_nf"], errors="coerce"
)
df_devolucao["dt_emis_nf"] = pd.to_datetime(df_devolucao["dt_emis_nf"], errors="coerce")

# Obter datas mínima e máxima
data_min = df_faturamento["dt_emis_nf"].min().date()
data_max = df_faturamento["dt_emis_nf"].max().date()

# Inputs do usuário para seleção de data
data_inicial = st.sidebar.date_input(
    "Data Inicial", value=data_min, min_value=data_min, max_value=data_max
)
data_final = st.sidebar.date_input(
    "Data Final", value=data_max, min_value=data_min, max_value=data_max
)

# Conversão para datetime
data_inicial = pd.to_datetime(data_inicial)
data_final = pd.to_datetime(data_final)

# 🔎 Filtragem por período
df_filtrado = df_faturamento[
    (df_faturamento["dt_emis_nf"] >= data_inicial)
    & (df_faturamento["dt_emis_nf"] <= data_final)
]

df_devolucao_filtrado = df_devolucao[
    (df_devolucao["dt_emis_nf"] >= data_inicial)
    & (df_devolucao["dt_emis_nf"] <= data_final)
]

# 🎯 Filtro Receita


# Se for "AMBOS", mantém o df_filtrado como está, sem alterações

# 🔵 Cores por marca
cores_marca = {
    "PAPAIZ": "blue",
    "YALE": "yellow",
    "LA FONTE": "darkred",
    "SILVANA": "orange",
    "VAULT": "gray",
    "Total": "darkgreen",
}


################ Aqui Começa o Código do Dashboard ################


# 💰 Cálculo do Faturamento Líquido
faturamento_marca = df_filtrado.groupby("marca")["vl_net_livro"].sum()
devolucao_marca = df_devolucao_filtrado.groupby("marca")["vl_net_livro"].sum()
devolucao_marca = devolucao_marca.reindex(faturamento_marca.index, fill_value=0)

# 🎯 Cálculo do faturamento líquido com cutoff editável
# Mapear valores de cutoff das marcas
cutoff_inicial_series = pd.Series(index=faturamento_marca.index, dtype=float)
cutoff_final_series = pd.Series(index=faturamento_marca.index, dtype=float)

for marca in faturamento_marca.index:
    # Normalizar nome da marca para buscar no JSON
    marca_normalizada = marca.replace("SILVANA CDSP", "SILVANA")
    
    if marca_normalizada in cutoff_dados:
        cutoff_inicial_series[marca] = cutoff_dados[marca_normalizada]["cutoff_inicial"]
        cutoff_final_series[marca] = cutoff_dados[marca_normalizada]["cutoff_final"]
    else:
        cutoff_inicial_series[marca] = 0.0
        cutoff_final_series[marca] = 0.0

# Calcular faturamento líquido: Faturamento Bruto + Cutoff Inicial - Devoluções - Cutoff Final
faturamento_liquido = (
    faturamento_marca 
    + cutoff_inicial_series.fillna(0) 
    - devolucao_marca 
    - cutoff_final_series.fillna(0)
).fillna(0)

# 🔄 Formatando resultado final
faturamento_liquido_marca = faturamento_liquido.reset_index()
faturamento_liquido_marca.columns = ["Marca", "Faturamento Líquido"]

######
# 🛒 Calculando tudo que já temos

df_resumo = (
    df_filtrado.groupby("marca")
    .agg(
        Quantidade_NFs=("nota_fiscal", lambda x: x.nunique()),
        Quantidade_SKUs=("item", "nunique"),
        Quantidade_Pecas=("quantidade", "sum"),
    )
    .reset_index()
)

faturamento_total = faturamento_liquido_marca["Faturamento Líquido"].sum()
qtd_nfs_unicas_total = df_resumo["Quantidade_NFs"].sum()
total_devolucao = df_devolucao_filtrado["vl_net_livro"].sum()


# 🔥 Criar cinco colunas lado a lado


#####
#

# 🔄 Agrupar faturamento diário
faturamento_diario = df_filtrado.groupby("dt_emis_nf", as_index=False)[
    "vl_net_livro"
].sum()

# 🪄 Formatar valores para tooltip e texto no gráfico
faturamento_diario["vl_formatado"] = faturamento_diario["vl_net_livro"].apply(
    lambda x: formatar_valor_seguro(x, "currency")
)

# 📈 Gráfico interativo com Plotly Express
fig_fat = px.line(
    faturamento_diario,
    x="dt_emis_nf",
    y="vl_net_livro",
    markers=True,
    title="📆 Faturamento Geral Diário",
    labels={"dt_emis_nf": "Data", "vl_net_livro": "Faturamento (R$)"},
    hover_data={"vl_net_livro": False, "vl_formatado": True},
    text="vl_formatado",  # 🎯 Mostrar o valor no ponto
)

# ✨ Personalização do layout
fig_fat.update_traces(
    line=dict(color="blue"),
    marker=dict(size=8),
    textposition="top center",  # Pode usar: 'top center', 'bottom center', 'middle right', etc.
    textfont=dict(size=10),
)

fig_fat.update_layout(
    xaxis_title="Data",
    yaxis_title="Faturamento (R$)",
    hoverlabel=dict(bgcolor="white", font_size=13, font_family="Arial"),
    xaxis=dict(tickangle=0),
    yaxis_tickprefix="R$ ",
    plot_bgcolor="#F9F9F9",
    margin=dict(t=50, b=30),
)


# Mostrar no Streamlit

# Título da seção

# 8️⃣ Exibir faturamento em cards no Streamlit

# 📊 Totais Principais - No Topo
st.subheader("📈 Resumo Geral")

# Calcular os totais
faturamento_bruto_total = df_filtrado.groupby("marca")["vl_net_livro"].sum().sum()
total_devolucoes_geral = df_devolucao_filtrado["vl_net_livro"].sum()

# Exibir totais em colunas
col_total1, col_total2, col_total3 = st.columns(3)

with col_total1:
    st.metric(
        "💵 Faturamento Bruto Total",
        formatar_valor_seguro(faturamento_bruto_total, "currency"),
    )

with col_total2:
    st.metric(
        "💰 Faturamento Líquido Total",
        formatar_valor_seguro(faturamento_total, "currency"),
    )

with col_total3:
    # CORREÇÃO: Usar o valor real das devoluções, não a diferença entre bruto e líquido
    total_devolucoes = total_devolucoes_geral
    st.metric(
        "🔻 Total Devoluções",
        formatar_valor_seguro(total_devolucoes, "currency"),
        delta=(
            f"-{(total_devolucoes/faturamento_bruto_total)*100:.1f}%"
            if faturamento_bruto_total > 0
            else "0%"
        ),
    )

st.markdown("---")

# 📋 Abas do Dashboard
tab_fat_liquido, tab_fat_bruto, tab_graficos, tab_cutoff = st.tabs(
    ["💰 Faturamento Líquido", "💵 Faturamento Bruto", "📊 Gráficos", "📋 Cutoff"]
)

with tab_fat_liquido:
    col_fat1, col_fat2 = st.columns([2, 1])

    with col_fat1:
        st.metric(
            "💰 Faturamento Total",
            formatar_valor_seguro(faturamento_total, "currency"),
        )

    with col_fat2:
        st.metric(
            "🧾 Notas Fiscais Emitidas", formatar_valor_seguro(qtd_nfs_unicas_total, "integer")
        )

    st.subheader("Faturamento Líquido por Marca")

    colunas = st.columns(
        min(len(faturamento_liquido), 6)
    )  # evita criar mais colunas que o necessário

    for i, (marca, valor) in enumerate(faturamento_liquido.items()):
        with colunas[i % len(colunas)]:
            st.markdown(f"**{marca}**")
            valor_formatado = formatar_valor_seguro(valor, "currency")
            st.write(valor_formatado)

with tab_fat_bruto:
    st.subheader("💵 Faturamento Bruto por Marca")
    st.caption("Valores antes do desconto de devoluções")

    # Calcular faturamento bruto por marca (apenas faturamento, sem devoluções)
    faturamento_bruto_marca = df_filtrado.groupby("marca")["vl_net_livro"].sum()

    colunas_bruto = st.columns(min(len(faturamento_bruto_marca), 6))

    for i, (marca, valor) in enumerate(faturamento_bruto_marca.items()):
        with colunas_bruto[i % len(colunas_bruto)]:
            st.markdown(f"**{marca}**")
            valor_formatado_bruto = formatar_valor_seguro(valor, "currency")
            st.write(valor_formatado_bruto)

            # Calcular e mostrar a diferença entre bruto e líquido (inclui devoluções + ajustes de cutoff)
            if marca in faturamento_liquido.index:
                diferenca = valor - faturamento_liquido[marca]
                if diferenca > 0:
                    st.caption(
                        f"🔻 Devoluções + Ajustes: {formatar_valor_seguro(diferenca, 'currency')}"
                    )
                else:
                    st.caption("✅ Sem devoluções/ajustes")

with tab_graficos:
    col1, col2 = st.columns(2)
    with col1:
        # 🔢 Preparar dados para o gráfico de rosca
        labels = faturamento_liquido_marca["Marca"]
        values = faturamento_liquido_marca["Faturamento Líquido"]
        colors = [cores_marca.get(marca, "lightgray") for marca in labels]

        # 🍩 Criar gráfico de rosca com Plotly
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.5,
                    marker=dict(colors=colors),
                    textinfo="label+percent",
                    hoverinfo="label+value",
                )
            ]
        )

        # 🎨 Layout do gráfico
        fig.update_layout(
            title_text="Faturamento Líquido por Marca",
            annotations=[
                dict(text="Total", x=0.5, y=0.5, font_size=18, showarrow=False)
            ],
            showlegend=True,
        )

        # 📺 Exibir gráfico no Streamlit
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 📊 Gráfico comparativo Bruto vs Líquido
        st.subheader("📊 Comparativo: Bruto vs Líquido")

        # Preparar dados para o gráfico comparativo
        faturamento_bruto_marca = df_filtrado.groupby("marca")["vl_net_livro"].sum()

        # Criar DataFrame para o gráfico
        df_comparativo = pd.DataFrame(
            {
                "Marca": faturamento_bruto_marca.index,
                "Faturamento Bruto": faturamento_bruto_marca.values,
                "Faturamento Líquido": [
                    faturamento_liquido.get(marca, 0)
                    for marca in faturamento_bruto_marca.index
                ],
            }
        )

        # Calcular devoluções + ajustes de cutoff
        df_comparativo["Devoluções + Ajustes"] = (
            df_comparativo["Faturamento Bruto"] - df_comparativo["Faturamento Líquido"]
        )

        # Criar gráfico de barras agrupadas
        fig_comparativo = go.Figure()

        # Adicionar barras de faturamento bruto
        fig_comparativo.add_trace(
            go.Bar(
                name="Faturamento Bruto",
                x=df_comparativo["Marca"],
                y=df_comparativo["Faturamento Bruto"],
                marker_color="lightblue",
                text=[
                    formatar_valor_seguro(v, "currency")
                    for v in df_comparativo["Faturamento Bruto"]
                ],
                textposition="outside",
            )
        )

        # Adicionar barras de faturamento líquido
        fig_comparativo.add_trace(
            go.Bar(
                name="Faturamento Líquido",
                x=df_comparativo["Marca"],
                y=df_comparativo["Faturamento Líquido"],
                marker_color="darkblue",
                text=[
                    formatar_valor_seguro(v, "currency")
                    for v in df_comparativo["Faturamento Líquido"]
                ],
                textposition="outside",
            )
        )

        # Configurar layout
        fig_comparativo.update_layout(
            title="Faturamento Bruto vs Líquido por Marca",
            xaxis_title="Marca",
            yaxis_title="Valor (R$)",
            barmode="group",
            yaxis_tickprefix="R$ ",
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(size=10),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            margin=dict(t=80, b=30, l=50, r=50),
        )

        st.plotly_chart(fig_comparativo, use_container_width=True)

with tab_cutoff:
    st.subheader("📋 Gerenciar Cutoff por Marca")
    st.markdown("---")
    
    # Criar formulário para edição de cutoff
    with st.form("cutoff_form"):
        st.markdown("### 🎯 Editar Valores de Cutoff")
        st.caption("Valores em reais (R$) - Cutoff Inicial é adicionado, Cutoff Final é subtraído do faturamento")
        
        cutoff_editado = {}
        
        # Criar inputs para cada marca
        col1, col2 = st.columns(2)
        
        marcas = ["LA FONTE", "PAPAIZ", "SILVANA", "VAULT"]
        
        for i, marca in enumerate(marcas):
            with col1 if i % 2 == 0 else col2:
                st.markdown(f"**{marca}**")
                
                # Valores atuais
                cutoff_atual = cutoff_dados.get(marca, {"cutoff_inicial": 0.0, "cutoff_final": 0.0})
                
                # Inputs para cutoff inicial e final
                cutoff_inicial = st.number_input(
                    f"Cutoff Inicial - {marca}",
                    value=float(cutoff_atual["cutoff_inicial"]),
                    step=1000.0,
                    format="%.2f",
                    key=f"cutoff_inicial_{marca}"
                )
                
                cutoff_final = st.number_input(
                    f"Cutoff Final - {marca}",
                    value=float(cutoff_atual["cutoff_final"]),
                    step=1000.0,
                    format="%.2f",
                    key=f"cutoff_final_{marca}"
                )
                
                cutoff_editado[marca] = {
                    "cutoff_inicial": cutoff_inicial,
                    "cutoff_final": cutoff_final
                }
                
                st.markdown("---")
        
        # Botão para salvar
        if st.form_submit_button("💾 Salvar Cutoff", use_container_width=True):
            if salvar_cutoff_editavel(cutoff_editado):
                st.success("✅ Cutoff salvo com sucesso!")
                st.rerun()
            else:
                st.error("❌ Erro ao salvar cutoff!")
    
    # Mostrar resumo dos valores atuais
    st.markdown("### 📊 Resumo Atual do Cutoff")
    
    # Criar DataFrame para exibição
    df_cutoff_resumo = []
    for marca, valores in cutoff_dados.items():
        df_cutoff_resumo.append({
            "Marca": marca,
            "Cutoff Inicial": formatar_valor_seguro(valores['cutoff_inicial'], "currency"),
            "Cutoff Final": formatar_valor_seguro(valores['cutoff_final'], "currency"),
            "Impacto Líquido": formatar_valor_seguro(valores['cutoff_inicial'] - valores['cutoff_final'], "currency")
        })
    
    df_cutoff_resumo = pd.DataFrame(df_cutoff_resumo)
    st.dataframe(df_cutoff_resumo, use_container_width=True)
    
    # Explicação do impacto
    st.markdown("### ℹ️ Como funciona o Cutoff")
    st.markdown("""
    - **Cutoff Inicial**: Valor adicionado ao faturamento (representa receitas pendentes do período anterior)
    - **Cutoff Final**: Valor subtraído do faturamento (representa receitas que serão realizadas no próximo período)  
    - **Impacto Líquido**: Cutoff Inicial - Cutoff Final (impacto total no faturamento líquido)
    - **Fórmula**: Faturamento Líquido = Faturamento Bruto + Cutoff Inicial - Devoluções - Cutoff Final
    """)


# Agrupando os dados
faturamento_marca_diario = df_filtrado.groupby(["dt_emis_nf", "marca"], as_index=False)[
    "vl_net_livro"
].sum()

# Formatando o valor para exibição
faturamento_marca_diario["vl_formatado"] = faturamento_marca_diario[
    "vl_net_livro"
].apply(lambda x: formatar_valor_seguro(x, "currency"))

# Criando o gráfico
fig_fat_marca = px.line(
    faturamento_marca_diario,
    x="dt_emis_nf",
    y="vl_net_livro",
    color="marca",
    markers=True,
    title="📆 Faturamento Diário por Marca",
    labels={"dt_emis_nf": "Data", "vl_net_livro": "Faturamento (R$)", "marca": "Marca"},
    hover_data={"vl_net_livro": False, "vl_formatado": True},
)

fig_fat_marca.update_traces(textposition="top center", textfont=dict(size=10))

fig_fat_marca.update_layout(
    xaxis_title="Data",
    yaxis_title="Faturamento (R$)",
    hoverlabel=dict(bgcolor="white", font_size=13, font_family="Arial"),
    xaxis=dict(tickangle=0),
    yaxis_tickprefix="R$ ",
    plot_bgcolor="#F9F9F9",
    margin=dict(t=50, b=30),
    legend_title_text="Marca",
)

# Exibindo o gráfico no app


# Agrupar faturamento bruto por canal
# Agrupar faturamento bruto por canal E marca
faturamento_bruto = (
    df_filtrado.groupby(["canal_venda_cliente", "marca"])["vl_net_livro"]
    .sum()
    .reset_index()
    .rename(columns={"vl_net_livro": "Faturamento"})
)

# Agrupar devoluções por canal E marca
devolucao_canal = (
    df_devolucao_filtrado.groupby(["canal_venda_cliente", "marca"])["vl_net_livro"]
    .sum()
    .reset_index()
    .rename(columns={"vl_net_livro": "Devolucao"})
)

# Juntar os dois DataFrames
faturamento_liquido = pd.merge(
    faturamento_bruto, devolucao_canal, on=["canal_venda_cliente", "marca"], how="left"
)

# Substituir NaN por 0 nas devoluções
faturamento_liquido["Devolucao"] = faturamento_liquido["Devolucao"].fillna(0)

# Calcular faturamento líquido
faturamento_liquido["Faturamento Líquido"] = (
    faturamento_liquido["Faturamento"] - faturamento_liquido["Devolucao"]
)

# Formatar valores para exibir na barra
faturamento_liquido["Faturamento Formatado"] = faturamento_liquido[
    "Faturamento Líquido"
].apply(lambda x: formatar_valor_seguro(x, "currency"))

# Renomear coluna de canal
faturamento_liquido.rename(
    columns={"canal_venda_cliente": "Canal de Venda"}, inplace=True
)

# Garantir que a coluna de data esteja só com a data (sem hora)
df_filtrado["data_apenas"] = df_filtrado["dt_emis_nf"].dt.date

# Filtrar pelas marcas desejadas
marcas_desejadas = ["PAPAIZ", "LA FONTE", "SILVANA", "VAULT"]
df_filtrado = df_filtrado[df_filtrado["marca"].isin(marcas_desejadas)]

# 🌟 AGREGAR por data e marca
df_agrupado = df_filtrado.groupby(["data_apenas", "marca"], as_index=False)[
    "vl_net_livro"
].sum()


# Pegando a data mais recente do df_agrupado
ultimo_dia = df_agrupado["data_apenas"].max()

# Filtrando apenas o faturamento do último dia
df_ultimo_dia = df_agrupado[df_agrupado["data_apenas"] == ultimo_dia]

# Criando o gráfico de barras horizontais (barra deitada)
fig_dia = px.bar(
    df_ultimo_dia,
    y="marca",  # 👈 Agora a marca é o eixo Y
    x="vl_net_livro",  # 👈 E o faturamento é o eixo X
    color="marca",
    color_discrete_map=cores_marca,
    labels={"marca": "Marca", "vl_net_livro": "Faturamento (R$)"},
    title=f"📅 Faturamento por Marca no Dia {ultimo_dia.strftime('%d/%m/%Y')}",
    hover_data={"vl_net_livro": ":.2f"},
    text_auto=".2s",  # Valores formatadinhos na ponta da barra
    height=500,
)

fig_dia.update_traces(
    textfont_size=10, textangle=0, textposition="outside", cliponaxis=False
)

fig_dia.update_layout(
    xaxis_title="Faturamento (R$)",
    yaxis_title="Marca",
    xaxis_tickangle=0,
    legend_title="Marca",
    bargap=0.2,
    template="plotly_white",
    showlegend=False,
)

col1, col2 = st.columns([3, 5])
with col2:
    st.plotly_chart(fig_dia, use_container_width=True)
with col1:
    st.subheader("📦 Resumo de Faturamento por Marca")

    # Formatação estilo Brasilzão 🇧🇷
    df_resumo["Quantidade_NFs"] = df_resumo["Quantidade_NFs"].apply(
        lambda x: formatar_valor_seguro(x, "integer")
    )
    df_resumo["Quantidade_SKUs"] = df_resumo["Quantidade_SKUs"].apply(
        lambda x: formatar_valor_seguro(x, "integer")
    )
    df_resumo["Quantidade_Pecas"] = df_resumo["Quantidade_Pecas"].apply(
        lambda x: formatar_valor_seguro(x, "integer")
    )

    st.dataframe(df_resumo, use_container_width=True)

    st.subheader("📊 Média de SKUs e Peças Faturadas por Funcionário")

    # Input: número de funcionários
    num_funcionarios = st.sidebar.number_input(
        "Funcionários no Período:", min_value=1, step=1, value=5
    )
    if num_funcionarios > 0:
        skus_por_marca = np.ceil(df_filtrado.groupby("marca")["item"].count() / num_funcionarios)
        pecas_por_marca = np.ceil(
            df_filtrado.groupby("marca")["quantidade"].sum() / num_funcionarios
        )

        df_resultado = pd.DataFrame(
            {
                "Marca": skus_por_marca.index,
                "SKUs por Funcionário": skus_por_marca.values,
                "Peças por Funcionário": pecas_por_marca.values,
            }
        ).reset_index(drop=True)

        # Formata os números para o padrão brasileiro
        df_resultado["SKUs por Funcionário"] = df_resultado[
            "SKUs por Funcionário"
        ].apply(
            lambda x: formatar_valor_seguro(x, "integer")
        )
        df_resultado["Peças por Funcionário"] = df_resultado[
            "Peças por Funcionário"
        ].apply(
            lambda x: formatar_valor_seguro(x, "integer")
        )

        st.dataframe(df_resultado, use_container_width=True)
    else:
        st.warning("👀 Defina um número válido de funcionários para ver as médias.")

# 🚀 Exibir no Streamlit

# Gráficos de Vendas

tab1_faturamento, tab3_marcas = st.tabs(["📈 Faturamento", "🏆 Faturamento por Marcas"])
with tab1_faturamento:
    st.subheader("Faturamento Geral Diário")
    st.plotly_chart(fig_fat, use_container_width=True)

with tab3_marcas:
    st.plotly_chart(fig_fat_marca, use_container_width=True)

st.subheader("📦 Faturamento Líquido por Canal de Venda")

# 📦 Obter todos os canais únicos disponíveis
canais_disponiveis = sorted(
    df_faturamento["canal_venda_cliente"].dropna().unique().tolist()
)

# 🏷️ Obter todas as marcas únicas disponíveis
marcas_disponiveis = sorted(df_faturamento["marca"].dropna().unique().tolist())

# 🧠 Inicializar valores no session_state (apenas uma vez)
if "canais_selecionados" not in st.session_state:
    st.session_state["canais_selecionados"] = canais_disponiveis
if "marcas_selecionadas" not in st.session_state:
    st.session_state["marcas_selecionadas"] = marcas_disponiveis
if "filtro_resetado" not in st.session_state:
    st.session_state["filtro_resetado"] = False

# 🔄 Botão de reset (ativa flag e força rerun)
# 🎛️ Layout dos filtros
col_filtro_btn, col_filtros = st.columns([1, 5])

with col_filtro_btn:
    if st.button("🔄 Resetar Filtros"):
        st.session_state["canais_selecionados"] = canais_disponiveis
        st.session_state["marcas_selecionadas"] = marcas_disponiveis
        st.session_state["filtro_resetado"] = True
        st.rerun()

# 📌 Define keys dinâmicos para controle dos filtros
key_canais = (
    "multiselect_filtro_canais_resetado"
    if st.session_state.get("filtro_resetado")
    else "multiselect_canais"
)
key_marcas = (
    "multiselect_filtro_marcas_resetado"
    if st.session_state.get("filtro_resetado")
    else "multiselect_marcas"
)

# 🧩 Filtros
canais_selecionados = st.multiselect(
    "Selecione os Canais de Venda para Análise",
    options=canais_disponiveis,
    default=st.session_state.get("canais_selecionados", canais_disponiveis),
    key=key_canais,
)

marcas_selecionadas = st.multiselect(
    "Selecione as Marcas para Análise",
    options=marcas_disponiveis,
    default=st.session_state.get("marcas_selecionadas", marcas_disponiveis),
    key=key_marcas,
)

# 🧠 Atualiza session_state após reset
if not st.session_state.get("filtro_resetado", False):
    st.session_state["canais_selecionados"] = canais_selecionados
    st.session_state["marcas_selecionadas"] = marcas_selecionadas
else:
    st.session_state["filtro_resetado"] = False

# 📉 Aplicar filtros no DataFrame
faturamento_filtrado = faturamento_liquido[
    (faturamento_liquido["Canal de Venda"].isin(canais_selecionados))
    & (faturamento_liquido["marca"].isin(marcas_selecionadas))
]

# 📊 Agrupar dados por Canal de Venda
faturamento_por_canal = faturamento_filtrado.groupby("Canal de Venda", as_index=False)[
    "Faturamento Líquido"
].sum()

# 💰 Formatar valores para exibição no gráfico
faturamento_por_canal["Faturamento Formatado"] = faturamento_por_canal[
    "Faturamento Líquido"
].apply(lambda x: formatar_valor_seguro(x, "currency"))

# 📈 Gráfico de Barras com Plotly
fig_fat_liquido = px.bar(
    faturamento_por_canal,
    x="Canal de Venda",
    y="Faturamento Líquido",
    text="Faturamento Formatado",
    color="Canal de Venda",
    color_discrete_sequence=px.colors.qualitative.Bold,
    title="💰 Faturamento Líquido por Canal de Venda (com devoluções)",
    labels={"Faturamento Líquido": "Faturamento Líquido (R$)"},
)

# 🧾 Ajustes visuais do gráfico
fig_fat_liquido.update_traces(
    textposition="outside", textfont=dict(size=10), cliponaxis=False
)

fig_fat_liquido.update_layout(
    yaxis_tickprefix="R$ ",
    xaxis_title="Canal de Venda",
    yaxis_title="Faturamento Líquido (R$)",
    showlegend=False,
    plot_bgcolor="#FFFFFF",
    margin=dict(t=50, b=30),
)

# 📺 Exibir gráfico no Streamlit
st.plotly_chart(fig_fat_liquido, use_container_width=True)


# COLUNA DO RESUMO


st.divider()


###############################  🔼🔼🔼  MÉDIA DE EMBARQUES POR DIA DA SEMANA 🔼🔼🔼  ##########################


##### GRAFICOS DO HOME2
import plotly.graph_objects as go

# --- Cálculo de embarques faturados por funcionário por marca ---
# Filtrar os dados para o período selecionado
df_periodo = df_faturamento[
    (df_faturamento["dt_emis_nf"] >= pd.to_datetime(data_inicial))
    & (df_faturamento["dt_emis_nf"] <= pd.to_datetime(data_final))
]

# Converter para formato aceito pelo np.busday_count
data_inicio_np = pd.to_datetime(data_inicial).date()
data_final_np = pd.to_datetime(data_final).date()

# Calcular o número de dias úteis no período
dias_uteis = np.busday_count(data_inicio_np, data_final_np)
if dias_uteis == 0:
    dias_uteis = 1  # Prevenção contra divisão por zero

# Agrupar por marca e contar os embarques faturados (considerando notas fiscais únicas)
embarques_por_marca = df_periodo.groupby("marca")["nota_fiscal"].nunique().reset_index()

# Criar um input no menu lateral para definir o número de funcionários
# (já foi feito acima, mas aqui só para referência)
# Calcular a média de embarques por funcionário para cada marca
embarques_por_marca["media_por_funcionario"] = np.ceil((
    embarques_por_marca["nota_fiscal"] / dias_uteis
) / num_funcionarios)  # Usando o input

# Calcular o total geral de embarques
total_embarque = df_periodo["nota_fiscal"].nunique()

# Calcular a média geral de embarques por funcionário
total_media = np.ceil((
    total_embarque / dias_uteis
) / num_funcionarios)  # Ajustado para usar o input

# Criar o DataFrame de total
df_total = pd.DataFrame(
    {
        "marca": ["Total"],
        "nota_fiscal": [total_embarque],
        "media_por_funcionario": [total_media],
    }
)

# Concatenar o total ao DataFrame original
embarques_por_marca = pd.concat([embarques_por_marca, df_total], ignore_index=True)

# Plotar o gráfico com Plotly
fig_media = px.bar(
    embarques_por_marca,
    x="marca",
    y="media_por_funcionario",
    title="Média de Embarques Faturados por Funcionário (por Marca)",
    text_auto=".0f",
    labels={
        "marca": "Marca",
        "media_por_funcionario": "Média de Embarques/Funcionário",
    },
    color="marca",
    color_discrete_map=cores_marca,
)


# --------------------------------
# Ajuste no cálculo de Peças Per Capta
# --------------------------------

# Calcular o total de peças
total_pecas = df_filtrado["quantidade"].sum()

# Calcular peças per capita dinamicamente
pecas_per_capta = np.ceil(total_pecas / num_funcionarios)  # Agora usa o input



# --------------------------------
# Ajuste no cálculo de Peças por Marca
# --------------------------------

# Agrupar os dados por marca e somar a quantidade total de peças faturadas
df_pecas_marca = df_filtrado.groupby("marca")["quantidade"].sum().reset_index()

# Calcular a quantidade per capita dinamicamente
df_pecas_marca["pecas_per_capta"] = np.ceil(
    df_pecas_marca["quantidade"] / num_funcionarios
)  # Agora usa o input

# Criar coluna formatada para exibição
df_pecas_marca["pecas_formatadas"] = df_pecas_marca["pecas_per_capta"].apply(
    lambda x: formatar_valor_seguro(x, "integer")
)

# Ordenar do maior para o menor
df_pecas_marca = df_pecas_marca.sort_values(by="pecas_per_capta", ascending=True)

# Criar gráfico de barras simples em vez de funil
fig_funnel = px.bar(
    df_pecas_marca,
    x="marca",
    y="pecas_per_capta",
    title="📦 Peças Faturadas Per Capta por Marca",
    labels={"pecas_per_capta": "Peças Per Capta", "marca": "Marca"},
    text="pecas_formatadas",  # Usar valores formatados no texto
    color="marca",
    color_discrete_map=cores_marca,
)

# Melhorar a formatação do gráfico
fig_funnel.update_traces(
    textposition="outside", textfont=dict(size=12, color="black"), cliponaxis=False
)

# Melhorar layout com formatação brasileira
fig_funnel.update_layout(
    yaxis=dict(
        tickformat=",.",  # Formato brasileiro para números
        separatethousands=True,
        title="Peças Per Capta",
    ),
    xaxis=dict(title="Marca"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(size=11),
    margin=dict(t=50, b=30, l=50, r=50),
    showlegend=False,
)

# --------------------------------
# Ajuste no cálculo de SKUs por funcionário
# --------------------------------

# Média de SKUs por Embarque:
df_sku_embarque = df_filtrado.groupby("nota_fiscal")["item"].nunique().reset_index()
media_skus_por_embarque = np.ceil(df_sku_embarque["item"].mean())

# SKUs per Capta:
total_skus = df_filtrado["item"].nunique()
skus_per_capta = np.ceil(total_skus / num_funcionarios)  # Agora usa o input

# Exibição dos Indicadores em KPI Cards
col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
with col_kpi1:
    st.metric(
        label="Média de SKUs por Embarque", value=formatar_valor_seguro(media_skus_por_embarque, "integer")
    )
with col_kpi2:
    st.metric(label="SKUs per Capta", value=formatar_valor_seguro(skus_per_capta, "integer"))
with col_kpi3:
    st.metric("Peças Faturadas Per Capta", formatar_valor_seguro(pecas_per_capta, "integer"))
# --------------------------------
# Ajuste no cálculo por marca
# --------------------------------

# Média de SKUs por Embarque por Marca
df_sku_embarque_marca = (
    df_filtrado.groupby(["marca", "nota_fiscal"])["item"].nunique().reset_index()
)
df_media_skus_por_embarque = (
    df_sku_embarque_marca.groupby("marca")["item"].apply(lambda x: np.ceil(x.mean())).reset_index()
)
df_media_skus_por_embarque.rename(
    columns={"item": "media_skus_por_embarque"}, inplace=True
)

# SKUs per Capta por Marca
df_skus_per_capta = df_filtrado.groupby("marca")["item"].nunique().reset_index()
df_skus_per_capta["skus_per_capta"] = np.ceil(
    df_skus_per_capta["item"] / num_funcionarios
)  # Agora usa o input

# --------------------------------
# Criar os Gráficos Atualizados
# --------------------------------

# Gráfico de barras - Média de SKU's por Embarque
fig_sku_embarque = px.bar(
    df_media_skus_por_embarque,
    x="marca",
    y="media_skus_por_embarque",
    title="📦 Média de SKUs por Embarque por Marca",
    labels={"media_skus_por_embarque": "Média de SKUs por Embarque", "marca": "Marca"},
    text_auto=".0f",
    color="marca",
    color_discrete_map=cores_marca,
)

# Gráfico de barras - SKUs per Capta
fig_sku_capta = px.bar(
    df_skus_per_capta,
    x="marca",
    y="skus_per_capta",
    title="👷‍♂️ SKUs per Capta por Marca",
    labels={"skus_per_capta": "SKUs per Capta", "marca": "Marca"},
    text_auto=".0f",
    color="marca",
    color_discrete_map=cores_marca,
)

# --------------------------------
# Exibir os Gráficos Lado a Lado no Streamlit
# --------------------------------
(
    col1,
    col2,
    col3,
    col4,
) = st.tabs(
    [
        "Média de SKUs por Embarque por Marca",
        "SKUs per Capta por Marca",
        "Peças Faturadas Per Capta",
        "Media de Embarques por Funcionário",
    ]
)

with col1:
    st.write(
        "📢 Mostra, em média, quantos SKUs diferentes (itens únicos) são incluídos por embarque em cada marca."
    )
    st.plotly_chart(fig_sku_embarque)
with col2:
    st.write("📢 Mostra quantos SKUs únicos cada funcionário está lidando por marca.")
    st.plotly_chart(fig_sku_capta)

with col3:
    st.write(
        "📢 Representa o volume total de peças faturadas dividido pelo número de funcionários."
    )
    st.plotly_chart(fig_funnel)

with col4:
    st.write("📢 Indica quantos embarques em média cada funcionário separa.")
    st.plotly_chart(fig_media)

####### GRAFICOS ACIMA AQUI, DO HOME 2
###### TOP ITENS FATURADOS ###############

st.subheader("📊 Top Itens Faturados")

# 🧼 Garantir que o SKU está como string
df_filtrado["item"] = df_filtrado["item"].astype(str)

# -------------------------------
# Top 10 SKUs mais Faturados (Geral)
# -------------------------------
df_top_skus = df_filtrado.groupby("item")["quantidade"].sum().reset_index()
df_top_skus_sorted = df_top_skus.sort_values(by="quantidade", ascending=False)
df_top_10_skus = df_top_skus_sorted.head(10)

fig_top_10_skus = px.bar(
    df_top_10_skus,
    x="item",
    y="quantidade",
    text="quantidade",
    title="🔥 Top 10 SKUs Mais Faturados (Geral)",
    labels={"quantidade": "Quantidade Faturada", "item": "SKU"},
    color="item",
    color_discrete_sequence=px.colors.qualitative.Set1,
)

fig_top_10_skus.update_traces(texttemplate="%{y:.0f}", textposition="outside")

# -------------------------------
# SKU Mais Faturado por Marca
# -------------------------------
df_sku_marca = df_filtrado.groupby(["marca", "item"])["quantidade"].sum().reset_index()
df_top_skus_por_marca = df_sku_marca.loc[
    df_sku_marca.groupby("marca")["quantidade"].idxmax()
]

fig_top_sku_marca = px.bar(
    df_top_skus_por_marca,
    x="marca",
    y="quantidade",
    text="item",
    color="marca",
    title="🏆 SKU Mais Faturado por Marca",
    labels={"quantidade": "Quantidade Faturada", "marca": "Marca"},
    color_discrete_sequence=px.colors.qualitative.Set1,
)

fig_top_sku_marca.update_traces(texttemplate="%{y:.0f}", textposition="outside")

# -------------------------------
# Top 5 SKUs por Marca (com Facet)
# -------------------------------
df_top_5_skus_por_marca = (
    df_sku_marca.groupby("marca")
    .apply(lambda x: x.nlargest(5, "quantidade"))
    .reset_index(drop=True)
)

fig_top_5_por_marca = px.bar(
    df_top_5_skus_por_marca,
    x="item",
    y="quantidade",
    color="marca",
    facet_col="marca",
    title="📊 Top 5 SKUs por Marca",
    labels={"quantidade": "Quantidade Faturada", "item": "SKU"},
    text="quantidade",
    color_discrete_sequence=px.colors.qualitative.Set1,
)

fig_top_5_por_marca.update_traces(texttemplate="%{y:.0f}", textposition="outside")
fig_top_5_por_marca.update_layout(showlegend=False)

# -------------------------------
# Exibir no Streamlit
# -------------------------------
tab1, tab2, tab3 = st.tabs(
    [
        "Top 10 por Marca",
        "Top 10 Geral",
        "SKU Mais Faturado por Marca",
    ]
)

with tab1:
    # 🔍 Filtro de Seleção de Marca na aba col3
    marcas_disponiveis = sorted(df_filtrado["marca"].dropna().unique())
    marca_selecionada = st.selectbox("Escolha a Marca", options=marcas_disponiveis)

    # 🧼 Filtrar os dados com base na marca selecionada
    df_faturado_filtrado_marca = df_filtrado[
        df_filtrado["marca"] == marca_selecionada
    ].copy()

    # ❌ Remover "CADEADO CR" dos dados da marca PAPAIZ
    if marca_selecionada == "PAPAIZ":
        df_faturado_filtrado_marca = df_faturado_filtrado_marca[
            ~df_faturado_filtrado_marca["desc_item"].str.contains(
                "CADEADO CR", case=False, na=False
            )
        ]

    # 🔢 Converter SKU para string (para evitar confusão no gráfico)
    df_faturado_filtrado_marca["item"] = df_faturado_filtrado_marca["item"].astype(str)

    # 📊 Agrupar os dados filtrados por SKU e somar as quantidades faturadas
    df_top_skus_marca = (
        df_faturado_filtrado_marca.groupby(["item", "desc_item"])["quantidade"]
        .sum()
        .reset_index()
    )

    # 📈 Ordenar os SKUs pela quantidade faturada de forma decrescente
    df_top_skus_marca_sorted = df_top_skus_marca.sort_values(
        by="quantidade", ascending=False
    )

    # 🥇 Selecionar os 10 SKUs mais faturados
    df_top_10_skus_marca = df_top_skus_marca_sorted.head(10)

    # 🎨 Gráfico de barras dos Top 10 SKUs da Marca Selecionada
    fig_top_10_skus_marca = px.bar(
        df_top_10_skus_marca,
        x="desc_item",
        y="quantidade",
        title=f"📊 Top 10 SKUs mais Faturados - Marca: {marca_selecionada}",
        labels={"quantidade": "Quantidade Faturada", "desc_item": "Descrição do Item"},
        color="item",
        color_discrete_sequence=px.colors.qualitative.Set1,
        text_auto=True,
    )

    fig_top_10_skus_marca.update_traces(texttemplate="%{y:.0f}")

    st.plotly_chart(fig_top_10_skus_marca, use_container_width=True)

with tab2:
    st.write(
        "📊 **Top 10 SKUs mais faturados em quantidade em todo o período selecionado**"
    )
    st.plotly_chart(fig_top_10_skus, use_container_width=True)

    # Mostrar tabela detalhada
    with st.expander("📋 Detalhes dos Top 10 SKUs", expanded=False):
        # Adicionar descrição dos itens
        df_top_10_com_desc = df_top_10_skus.merge(
            df_filtrado[["item", "desc_item"]].drop_duplicates(), on="item", how="left"
        )

        df_top_10_com_desc = df_top_10_com_desc[
            ["item", "desc_item", "quantidade"]
        ].rename(
            columns={
                "item": "SKU",
                "desc_item": "Descrição",
                "quantidade": "Quantidade Total",
            }
        )

        # Formatar quantidade
        df_top_10_com_desc["Quantidade Total"] = df_top_10_com_desc[
            "Quantidade Total"
        ].apply(lambda x: formatar_valor_seguro(x, "integer"))

        st.dataframe(df_top_10_com_desc, use_container_width=True)

with tab3:
    st.write("🏆 **SKU com maior quantidade faturada em cada marca**")
    st.plotly_chart(fig_top_sku_marca, use_container_width=True)

    # Mostrar tabela detalhada
    with st.expander("📋 Detalhes por Marca", expanded=False):
        # Adicionar descrição dos itens
        df_top_marca_com_desc = df_top_skus_por_marca.merge(
            df_filtrado[["item", "desc_item"]].drop_duplicates(), on="item", how="left"
        )

        df_top_marca_com_desc = df_top_marca_com_desc[
            ["marca", "item", "desc_item", "quantidade"]
        ].rename(
            columns={
                "marca": "Marca",
                "item": "SKU",
                "desc_item": "Descrição",
                "quantidade": "Quantidade",
            }
        )

        # Formatar quantidade
        df_top_marca_com_desc["Quantidade"] = df_top_marca_com_desc["Quantidade"].apply(
            lambda x: formatar_valor_seguro(x, "integer")
        )

        st.dataframe(df_top_marca_com_desc, use_container_width=True)

############### CURVA ABC #######################

st.subheader("📈 Curva ABC por Marca (Detalhado por Item)")

# 🔍 Seletor de marca
marca_selecionada_abc = st.selectbox(
    "Selecione a Marca para ver a Curva ABC",
    options=marcas_disponiveis,
    key="abc_detalhado",
)

# 🔢 Seletor para Top N SKUs
top_n = st.slider(
    "Selecione quantos SKUs exibir no gráfico (Top N)",
    min_value=10,
    max_value=100,
    value=20,
    step=10,
)

# ⚙️ Sliders de percentuais de corte
col1, col2 = st.columns(2)
with col1:
    limite_a = (
        st.slider(
            "Percentual acumulado para Classe A (%)",
            min_value=50,
            max_value=90,
            value=80,
            step=1,
        )
        / 100
    )
with col2:
    limite_b = (
        st.slider(
            "Percentual acumulado para Classe B (%)",
            min_value=int(limite_a * 100) + 1,
            max_value=99,
            value=95,
            step=1,
        )
        / 100
    )

# 🧼 Filtrar dados da marca
df_marca_abc = df_filtrado[df_filtrado["marca"] == marca_selecionada_abc].copy()
df_marca_abc["item"] = df_marca_abc["item"].astype(str)

# 🧮 Agrupar por item
df_abc_marca_full = (
    df_marca_abc.groupby(["item", "desc_item"])["quantidade"].sum().reset_index()
)
df_abc_marca_full = df_abc_marca_full.sort_values(
    by="quantidade", ascending=False
).reset_index(drop=True)

# ➕ Cálculos de percentuais
df_abc_marca_full["quantidade_acumulada"] = df_abc_marca_full["quantidade"].cumsum()
df_abc_marca_full["percentual"] = (
    df_abc_marca_full["quantidade"] / df_abc_marca_full["quantidade"].sum()
)
df_abc_marca_full["percentual_acumulado"] = df_abc_marca_full["percentual"].cumsum()


# 🅰️🅱️🅲️ Classificação dinâmica
def classificar_abc(p):
    if p <= limite_a:
        return "A"
    elif p <= limite_b:
        return "B"
    else:
        return "C"


df_abc_marca_full["classe_abc"] = df_abc_marca_full["percentual_acumulado"].apply(
    classificar_abc
)

# 🔢 Manter apenas os N primeiros para visualização
df_abc_marca = df_abc_marca_full.head(top_n).copy()

# 📛 Nome amigável para o gráfico
df_abc_marca["item_nome"] = (
    df_abc_marca["item"] + " - " + df_abc_marca["desc_item"].str.slice(0, 30)
)

# 📈 Gráfico de barras com linha de % acumulado
fig_abc_detalhado = px.bar(
    df_abc_marca,
    x="item_nome",
    y="quantidade",
    color="classe_abc",
    title=f"📦 Curva ABC - Marca: {marca_selecionada_abc}",
    labels={"quantidade": "Quantidade Faturada", "item_nome": "SKU / Descrição"},
    text="classe_abc",
    color_discrete_map={"A": "green", "B": "orange", "C": "red"},
)

fig_abc_detalhado.add_scatter(
    x=df_abc_marca["item_nome"],
    y=df_abc_marca["percentual_acumulado"],
    mode="lines+markers",
    name="Percentual Acumulado",
    yaxis="y2",
)

fig_abc_detalhado.update_layout(
    yaxis=dict(title="Quantidade Faturada"),
    yaxis2=dict(title="", overlaying="y", side="right", tickformat=".0%"),
    xaxis_tickangle=45,
    showlegend=True,
)

st.plotly_chart(fig_abc_detalhado, use_container_width=True)

# 📋 Tabela detalhada
st.markdown("### 📄 Detalhamento da Curva ABC")
st.dataframe(
    df_abc_marca[
        ["item", "desc_item", "quantidade", "percentual_acumulado", "classe_abc"]
    ].rename(
        columns={
            "item": "SKU",
            "desc_item": "Descrição do Item",
            "quantidade": "Qtd. Faturada",
            "percentual_acumulado": "% Faturamento Acumulado",
            "classe_abc": "Classe ABC",
        }
    ),
    use_container_width=True,
)
