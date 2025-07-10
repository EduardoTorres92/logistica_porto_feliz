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


# 🎯 Configuração inicial da página
st.set_page_config(page_title="Logística Assa Abloy", page_icon="🎯", layout="wide")

st.title("📈 Dashboard CD - Devoluções")

# ==================== FUNÇÕES DE TRATAMENTO DE DADOS ====================

def processar_dados_devolucao(df):
    """Aplica tratamentos específicos para dados de devolução"""
    
    # Converter receita para boolean se necessário
    if "receita" in df.columns:
        # Se a coluna receita contém strings, converter para boolean
        if df["receita"].dtype == 'object':
            df["receita"] = (
                df["receita"]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({"sim": True, "não": False, "nan": False})
                .fillna(False)
                .astype(bool)
            )
        # Se já é numérica, converter para boolean
        elif df["receita"].dtype in ['int64', 'float64']:
            df["receita"] = df["receita"].fillna(0).astype(bool)
    
    return df

# ==================== CARREGAMENTO DE DADOS ====================

@st.cache_data
def carregar_faturamento():
    arquivo_parquet = Path("Datasets/ESFT/ESFT0100_atual.parquet")
    if arquivo_parquet.exists():
        return pd.read_parquet(arquivo_parquet)
    else:
        st.warning("⚠️ Nenhum arquivo de dados encontrado. Faça upload de um arquivo CSV no dashboard principal.")
        return pd.DataFrame()

df_devolucao = carregar_faturamento()

if df_devolucao.empty:
    st.warning("📁 **Nenhum dado disponível**")
    st.info("👆 Faça upload de um arquivo CSV no dashboard principal para começar")
    st.stop()

# Aplicar tratamentos nos dados
df_devolucao = processar_dados_devolucao(df_devolucao)

# Tentar carregar cutoff (opcional)
try:
    df_cutoff = pd.read_excel("Datasets/ESFT/Cuttoff.xlsx", skiprows=1)
except:
    df_cutoff = pd.DataFrame()
    st.sidebar.warning("⚠️ Arquivo de cutoff não encontrado")

# Devolução
df_devolucao = df_devolucao[df_devolucao["tipo_oper"] == "5 - Dev Venda"]

# 🎯 Limpeza de Marcas
marcas_excluidas = ["PORTO FELIZ", "METALIKA", "YALE"]

# Normalize o nome das marcas para upper case
df_devolucao["marca"] = df_devolucao["marca"].str.upper()

# Remover marcas indesejadas
df_devolucao = df_devolucao[~df_devolucao["marca"].isin(marcas_excluidas)]

# 📅 Configuração de Datas
st.sidebar.subheader("📅 Selecione um Período para Análise")

# Garantir formato datetime nas datas
df_devolucao["dt_emis_nf"] = pd.to_datetime(df_devolucao["dt_emis_nf"], errors="coerce")

# Obter datas mínima e máxima
data_min = df_devolucao["dt_emis_nf"].min().date()
data_max = df_devolucao["dt_emis_nf"].max().date()

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
df_filtrado = df_devolucao[
    (df_devolucao["dt_emis_nf"] >= data_inicial)
    & (df_devolucao["dt_emis_nf"] <= data_final)
]

df_devolucao_filtrado = df_devolucao[
    (df_devolucao["dt_emis_nf"] >= data_inicial)
    & (df_devolucao["dt_emis_nf"] <= data_final)
]

# 🎯 Filtro Receita - CORRIGIDO

opcoes_receita = ["RECEITA SIM", "RECEITA NÃO", "AMBOS"]
filtro_receita = st.sidebar.radio("Escolha o filtro de Receita", opcoes_receita)

if filtro_receita == "RECEITA SIM":
    df_filtrado = df_filtrado[df_filtrado["receita"] == True]
elif filtro_receita == "RECEITA NÃO":
    df_filtrado = df_filtrado[df_filtrado["receita"] == False]
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

# --- Gráfico de Barras ---
# Criar DataFrames agregados para devoluções por marca e canal
devolucao_marca = df_devolucao_filtrado["marca"].value_counts().reset_index()
devolucao_marca.columns = ["Marca", "Quantidade"]


# Agrupar por marca e somar os valores das devoluções
valor_devolucao_marca = (
    df_devolucao_filtrado.groupby("marca")["vl_net_livro"].sum().reset_index()
)
valor_devolucao_marca.columns = ["Marca", "Valor Total"]

# Ordenar para melhor visualização
valor_devolucao_marca = valor_devolucao_marca.sort_values(
    by="Valor Total", ascending=False
)

# Formatar os valores com símbolo de moeda
valor_devolucao_marca["Valor Formatado"] = valor_devolucao_marca["Valor Total"].apply(
    lambda x: format_currency(x, "BRL", locale="pt_BR")
)

# Gráfico de barras com Plotly
fig_valor = px.bar(
    valor_devolucao_marca,
    x="Marca",
    y="Valor Total",
    color="Marca",
    text="Valor Formatado",
    title="💸 Valor Total em Devoluções por Marca",
    color_discrete_map=cores_marca,
)

fig_valor.update_traces(textposition="outside")
fig_valor.update_layout(xaxis_title="Marca", yaxis_title="Valor (R$)", showlegend=False)

# Exibir no Streamlit

# 🔢 Cálculo do valor total devolvido
total_devolvido = valor_devolucao_marca["Valor Total"].sum()

# 🧮 Cálculo do percentual por marca
valor_devolucao_marca["Percentual"] = (
    valor_devolucao_marca["Valor Total"] / total_devolvido
) * 100

# Formatar o percentual com 1 casa decimal
valor_devolucao_marca["% Formatado"] = valor_devolucao_marca["Percentual"].apply(
    lambda x: f"{x:.1f}%"
)

# 🍩 Gráfico de pizza com Plotly
fig_pct = px.pie(
    valor_devolucao_marca,
    names="Marca",
    values="Percentual",
    title="📊 Percentual de Devolução por Marca (R$)",
    color="Marca",
    color_discrete_map=cores_marca,
    hole=0.4,
)

fig_pct.update_traces(textinfo="percent+label")

# Mostrar no Streamlit


graf1, graf2 = st.columns(2)
with graf1:
    st.subheader("💸 Valor Total em Devoluções por Marca")
    st.plotly_chart(fig_valor, use_container_width=True)
with graf2:
    st.subheader("📊 Percentual de Devolução por Marca (R$)")
    st.plotly_chart(fig_pct, use_container_width=True)

# Agrupar por canal de venda e somar os valores devolvidos
devolucao_canal = (
    df_devolucao_filtrado.groupby("canal_venda_cliente")["vl_net_livro"]
    .sum()
    .reset_index()
)
devolucao_canal.columns = ["Canal de Venda", "Valor Total"]

# Formatar valor com moeda (opcional, só pra tabela, se quiser)
devolucao_canal["Valor Formatado"] = devolucao_canal["Valor Total"].apply(
    lambda x: format_currency(x, "BRL", locale="pt_BR")
)

# Gráfico de barras
fig_canal = px.bar(
    devolucao_canal,
    x="Canal de Venda",
    y="Valor Total",
    text="Valor Formatado",
    title="📦 Valor Total em Devoluções por Canal de Venda",
    color="Canal de Venda",
)

fig_canal.update_traces(textposition="outside")
fig_canal.update_layout(
    xaxis_title="Canal de Venda", yaxis_title="Valor (R$)", showlegend=False
)

# Exibir no Streamlit
st.subheader("📦 Devoluções por Canal de Venda")
st.plotly_chart(fig_canal, use_container_width=True)


#############

# Criar coluna 'Ano-Mês' no DataFrame
df_devolucao["Ano-Mês"] = df_devolucao["dt_emis_nf"].dt.to_period("M").astype(str)

# Agrupar por marca e mês
evolucao_mensal = (
    df_devolucao.groupby(["Ano-Mês", "marca"])["vl_net_livro"].sum().reset_index()
)

# Gráfico de linha com Plotly
fig_mensal = px.line(
    evolucao_mensal,
    x="Ano-Mês",
    y="vl_net_livro",
    color="marca",
    title="📆 Evolução Mensal de Devoluções por Marca",
    markers=True,
    color_discrete_map=cores_marca,
)

fig_mensal.update_layout(xaxis_title="Mês", yaxis_title="Valor Devolvido (R$)")

# Mostrar no Streamlit


#############

# Agrupar por marca e data
evolucao_dia = (
    df_devolucao_filtrado.groupby(["dt_emis_nf", "marca"])["vl_net_livro"]
    .sum()
    .reset_index()
)

# Gráfico de linha com Plotly
fig_diaria = px.line(
    evolucao_dia,
    x="dt_emis_nf",
    y="vl_net_livro",
    color="marca",
    title="📅 Evolução Diária de Devoluções por Marca",
    markers=True,
    color_discrete_map=cores_marca,
)

fig_diaria.update_layout(xaxis_title="Data", yaxis_title="Valor Devolvido (R$)")


tab1, tab2 = st.tabs(
    [
        "📅 Evolução Diária de Devoluções por Marca",
        "📆 Evolução Mensal de Devoluções por Marca",
    ]
)
with tab1:
    st.subheader("📅 Evolução Diária de Devoluções por Marca")
    st.plotly_chart(fig_diaria, use_container_width=True)
with tab2:
    st.subheader("📆 Evolução Mensal de Devoluções por Marca")
    st.plotly_chart(fig_mensal, use_container_width=True)

st.subheader("📦 Devoluções por Marca")
st.write(devolucao_marca)

st.divider()  # Adiciona uma linha separadora

# Criar DataFrames agregados para devoluções por marca e canal
devolucao_marca = df_devolucao_filtrado["marca"].value_counts().reset_index()
devolucao_marca.columns = ["Marca", "Quantidade"]

devolucao_canal = (
    df_devolucao_filtrado["canal_venda_cliente"].value_counts().reset_index()
)
devolucao_canal.columns = ["Canal de Venda", "Quantidade"]

# 🥧 Gráfico de devolução por marca (estilo pizza)
fig_marca_pizza = px.pie(
    devolucao_marca,
    names="Marca",
    values="Quantidade",
    title="🥧 Distribuição de Devoluções por Marca",
    color_discrete_map=cores_marca,
    hole=0.3,  # 👈 opcional: vira uma rosquinha 🍩
)

# ✨ Rótulos e layout
fig_marca_pizza.update_traces(textinfo="label+percent+value", textfont_size=14)
fig_marca_pizza.update_layout(
    showlegend=True, margin=dict(t=50, b=30), template="plotly_white"
)

# Mostrar no Streamlit


# 📊 Gráfico de devolução por canal de venda
fig_canal = px.bar(
    devolucao_canal,
    x="Canal de Venda",
    y="Quantidade",
    title=" Quantidade de Devoluções por Canal de Venda",
    text_auto=True,  # Mostra os valores nas barras
    labels={"Quantidade": "Qtd. Devoluções"},
    color="Canal de Venda",  # Cor individual por canal
    color_discrete_sequence=px.colors.sequential.Greens_r,
    height=500,
)

# ✨ Ajustes finos
fig_canal.update_traces(textposition="outside")
fig_canal.update_layout(
    xaxis_tickangle=45,
    yaxis_title="Quantidade",
    xaxis_title=None,
    showlegend=False,
    template="plotly_white",
    margin=dict(t=50, b=30),
)

# 💸 Agrupar valor total devolvido por marca
valor_devolucao_marca = (
    df_devolucao_filtrado.groupby("marca")["vl_net_livro"]
    .sum()
    .reset_index()
    .rename(columns={"marca": "Marca", "vl_net_livro": "Valor Devolvido"})
)
# 👑 Formatar os valores em R$
valor_devolucao_marca["Valor Formatado"] = valor_devolucao_marca[
    "Valor Devolvido"
].apply(lambda x: format_currency(x, "BRL", locale="pt_BR"))
# ✅ Adicionar linha com o total geral
total_geral = valor_devolucao_marca["Valor Devolvido"].sum()
linha_total = pd.DataFrame([{"Marca": "TOTAL", "Valor Devolvido": total_geral}])
# Criar linha total
total_geral = valor_devolucao_marca["Valor Devolvido"].sum()
linha_total = pd.DataFrame(
    [
        {
            "Marca": "TOTAL",
            "Valor Devolvido": total_geral,
            "Valor Formatado": format_currency(
                total_geral, "BRL", locale="pt_BR"
            ),  # 👈 Adiciona aqui também!
        }
    ]
)


# Concatenar com o DataFrame original
valor_devolucao_marca = pd.concat(
    [valor_devolucao_marca, linha_total], ignore_index=True
)

# 📊 Gráfico de barras com Plotly Express
fig_valor = px.bar(
    valor_devolucao_marca,
    x="Marca",
    y="Valor Devolvido",
    text_auto=True,
    title="💸 Valor Total em Devoluções por Marca",
    color="Marca",
    color_discrete_map=cores_marca,
    labels={"Valor Devolvido": "Valor (R$)"},
    height=500,
)

# 🎨 Plotly com os R$ bonitões no topo
fig_valor = px.bar(
    valor_devolucao_marca,
    x="Marca",
    y="Valor Devolvido",
    text="Valor Formatado",  # 👈 Aqui está a estrela!
    color="Marca",
    color_discrete_map=cores_marca,
    title="💸 Valor Total em Devoluções por Marca",
    labels={"Valor Devolvido": "Valor (R$)"},
    height=500,
)

fig_valor.update_traces(textposition="outside", textfont_size=10)
fig_valor.update_layout(
    xaxis_title="",
    yaxis_title="Valor (R$)",
    xaxis_tickangle=45,
    uniformtext_minsize=8,
    uniformtext_mode="hide",
    template="plotly_white",
)

# 🌟 Mostrar no Streamlit
# st.plotly_chart(fig_valor, use_container_width=True)

###########


# 📊 Agrupar por data e marca
devolucao_dia_marca = (
    df_devolucao_filtrado.groupby(["dt_emis_nf", "marca"])["vl_net_livro"]
    .sum()
    .reset_index()
    .rename(
        columns={
            "dt_emis_nf": "Data",
            "vl_net_livro": "Valor Devolvido",
            "marca": "Marca",
        }
    )
)

# 🎨 Gráfico de linha com cor por marca
fig_linha_marca = px.line(
    devolucao_dia_marca,
    x="Data",
    y="Valor Devolvido",
    color="Marca",
    markers=True,
    title="📈 Valor de Devoluções por Dia e por Marca",
    labels={"Valor Devolvido": "Valor (R$)", "Data": "Data"},
    color_discrete_map=cores_marca,
    template="plotly_white",
)

fig_linha_marca.update_traces(line_width=2)
fig_linha_marca.update_layout(margin=dict(t=50, b=30))

# Mostrar no Streamlit
# st.plotly_chart(fig_linha_marca, use_container_width=True)

from babel.dates import format_date

# 📄 Selecionar colunas e renomear
df_detalhe_devolucao = df_devolucao_filtrado[
    ["razao_social", "item", "quantidade", "vl_net_livro", "marca", "dt_emis_nf"]
].rename(
    columns={
        "razao_social": "Cliente",
        "item": "Item",
        "quantidade": "Quantidade",
        "vl_net_livro": "Valor",
        "marca": "BU",
        "dt_emis_nf": "Data da Devolução",
    }
)

# 💰 Formatando o valor diretamente na própria coluna "Valor"
df_detalhe_devolucao["Valor"] = df_detalhe_devolucao["Valor"].apply(
    lambda x: format_currency(x, "BRL", locale="pt_BR")
)

# 📅 Limpando a data (só data, sem hora)
df_detalhe_devolucao["Data da Devolução"] = pd.to_datetime(
    df_detalhe_devolucao["Data da Devolução"]
).dt.date  # só a data

# Mostrar no Streamlit
st.subheader("📄 Itens Devolvidos por Cliente")
st.dataframe(df_detalhe_devolucao, use_container_width=True)

# 🔍 Filtro de Seleção de Marca
marcas_disponiveis = sorted(df_devolucao_filtrado["marca"].dropna().unique())
marca_selecionada_dev = st.selectbox(
    "Escolha a Marca para ver os Itens mais Devolvidos", options=marcas_disponiveis
)

# 🧼 Filtrar os dados com base na marca selecionada
df_devolucao_filtrado_marca = df_devolucao_filtrado[
    df_devolucao_filtrado["marca"] == marca_selecionada_dev
].copy()

# ❌ Remover "CADEADO CR" dos dados da marca PAPAIZ, se quiser manter a limpeza
if marca_selecionada_dev == "PAPAIZ":
    df_devolucao_filtrado_marca = df_devolucao_filtrado_marca[
        ~df_devolucao_filtrado_marca["desc_item"].str.contains(
            "CADEADO CR", case=False, na=False
        )
    ]

# 🧠 Converter o código do item pra string
df_devolucao_filtrado_marca["item"] = df_devolucao_filtrado_marca["item"].astype(str)

# 📊 Agrupar os dados por SKU e somar as devoluções
df_top_skus_devolucao = (
    df_devolucao_filtrado_marca.groupby(["item", "desc_item"])["quantidade"]
    .sum()
    .reset_index()
)

# 🔢 Ordenar por quantidade devolvida
df_top_skus_devolucao = df_top_skus_devolucao.sort_values(
    by="quantidade", ascending=False
)

# 🥇 Pegar os Top 10
df_top_10_skus_devolucao = df_top_skus_devolucao.head(10)

# 🎨 Gráfico de barras para os Top 10 itens mais devolvidos
fig_top_10_devolucao = px.bar(
    df_top_10_skus_devolucao,
    x="desc_item",
    y="quantidade",
    title=f"🔁 Top 10 Itens mais Devolvidos - Marca: {marca_selecionada_dev}",
    labels={"quantidade": "Quantidade Devolvida", "desc_item": "Descrição do Item"},
    color="item",
    color_discrete_sequence=px.colors.qualitative.Set1,
    text_auto=True,
)

fig_top_10_devolucao.update_traces(texttemplate="%{y:.0f}")
fig_top_10_devolucao.update_layout(xaxis_tickangle=45)

# Mostrar no Streamlit
st.plotly_chart(fig_top_10_devolucao, use_container_width=True)
