import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Termômetro do Trader", layout="wide")

st.title("🌡️ Termômetro do Trader")
st.write("Controle de banca, disciplina, direção do mercado (Candle 9 / 10:15) e risco do dia.")

# === FUNÇÕES DE CARGA ===
@st.cache_data
def carregar_trades(caminho: str = "trades.csv") -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["data"])
    df = df.sort_values("data")
    return df

@st.cache_data
def carregar_contexto(caminho: str = "contexto_dia.csv") -> pd.DataFrame:
    df_ctx = pd.read_csv(caminho, parse_dates=["data"])
    df_ctx = df_ctx.sort_values("data")
    return df_ctx

# === CARREGANDO DADOS ===
try:
    df = carregar_trades()
except FileNotFoundError:
    st.error("Arquivo 'trades.csv' não encontrado na pasta do projeto.")
    st.stop()
except Exception as e:
    st.error(f"Erro ao carregar 'trades.csv': {e}")
    st.stop()

try:
    df_ctx = carregar_contexto()
except FileNotFoundError:
    df_ctx = None
except Exception as e:
    st.warning(f"Erro ao carregar 'contexto_dia.csv': {e}")
    df_ctx = None

# === SIDEBAR ===
st.sidebar.header("Configuração da Banca e Filtros")

banca_inicial = st.sidebar.number_input(
    "Banca inicial (R$)", min_value=0.0, value=200.0, step=50.0
)

# Filtros de data
datas_disponiveis = df["data"].dt.date.unique()
data_inicial = st.sidebar.date_input(
    "Data inicial (filtro trades)", 
    value=min(datas_disponiveis) if len(datas_disponiveis) > 0 else None
)
data_final = st.sidebar.date_input(
    "Data final (filtro trades)", 
    value=max(datas_disponiveis) if len(datas_disponiveis) > 0 else None
)

ativo_filtro = st.sidebar.text_input("Filtrar por ativo (ex: WIN)", value="")

# Filtro de dia para o Termômetro
data_termometro = st.sidebar.selectbox(
    "Dia para análise do Termômetro",
    options=datas_disponiveis,
    index=len(datas_disponiveis) - 1 if len(datas_disponiveis) > 0 else 0
)

# === APLICAR FILTROS NOS TRADES ===
df_filtrado = df.copy()

if data_inicial:
    df_filtrado = df_filtrado[df_filtrado["data"].dt.date >= data_inicial]
if data_final:
    df_filtrado = df_filtrado[df_filtrado["data"].dt.date <= data_final]
if ativo_filtro.strip():
    df_filtrado = df_filtrado[
        df_filtrado["ativo"].str.contains(ativo_filtro.strip(), case=False)
    ]

if df_filtrado.empty:
    st.info("Nenhum trade encontrado com os filtros atuais.")
    st.stop()

# === CÁLCULOS DA BANCA E RESUMO POR DIA ===
df_dias = df_filtrado.groupby("data", as_index=False).agg(
    lucro_dia=("resultado_r", "sum"),
    qtd_trades=("resultado_r", "count"),
    media_disciplina=("disciplina", "mean"),
)

saldos = []
banca_atual = banca_inicial

for _, row in df_dias.iterrows():
    lucro_dia = row["lucro_dia"]
    saldo_inicio_dia = banca_atual
    banca_atual = banca_atual + lucro_dia
    perc_dia = lucro_dia / saldo_inicio_dia if saldo_inicio_dia != 0 else np.nan

    saldos.append(
        {
            "data": row["data"],
            "lucro_dia": lucro_dia,
            "qtd_trades": row["qtd_trades"],
            "media_disciplina": row["media_disciplina"],
            "banca_inicio_dia": saldo_inicio_dia,
            "banca_fim_dia": banca_atual,
            "perc_dia": perc_dia * 100,
        }
    )

df_equity = pd.DataFrame(saldos)

if df_equity.empty:
    st.info("Sem dados de equity para os filtros selecionados.")
    st.stop()

banca_final = df_equity["banca_fim_dia"].iloc[-1]
lucro_total = banca_final - banca_inicial
perc_total = (lucro_total / banca_inicial) * 100 if banca_inicial != 0 else np.nan

# === CARDS GERAIS ===
st.subheader("📊 Visão Geral")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Banca inicial", f"R$ {banca_inicial:,.2f}")
col2.metric("Banca atual", f"R$ {banca_final:,.2f}", f"{lucro_total:,.2f} R$")
col3.metric("% acumulado", f"{perc_total:,.2f}%")
col4.metric("Total de trades (filtro)", int(df_filtrado.shape[0]))

# === TABELA RESUMO POR DIA ===
st.subheader("Resumo por dia (lucro, % e disciplina)")
st.dataframe(
    df_equity[
        ["data", "lucro_dia", "perc_dia", "qtd_trades", "media_disciplina"]
    ].rename(
        columns={
            "data": "Data",
            "lucro_dia": "Lucro do dia (R$)",
            "perc_dia": "% do dia",
            "qtd_trades": "Qtde trades",
            "media_disciplina": "Disciplina média",
        }
    ),
    use_container_width=True,
)

# === GRÁFICOS ===
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Evolução da Banca (Equity Curve)")
    st.line_chart(df_equity.set_index("data")["banca_fim_dia"])

with col_g2:
    st.subheader("Lucro por Dia")
    st.bar_chart(df_equity.set_index("data")["lucro_dia"])

# === TRADES DETALHADOS ===
st.subheader("Trades detalhados (após filtros)")
st.dataframe(df_filtrado, use_container_width=True)

# === TERMÔMETRO DO TRADER (POR DIA) ===
st.subheader(f"🌡️ Termômetro do Trader - {data_termometro}")

linha_dia = df_equity[df_equity["data"].dt.date == data_termometro]
if linha_dia.empty:
    st.warning("Não há dados de equity para o dia selecionado no Termômetro.")
else:
    linha_dia = linha_dia.iloc[0]

    # --- Disciplina ---
    disciplina_media = linha_dia["media_disciplina"]  # 0–10
    score_disciplina = disciplina_media * 10  # 0–100 base
    # Peso 40%
    peso_disciplina = 40
    contrib_disciplina = (score_disciplina / 100) * peso_disciplina

    # --- Resultado do dia ---
    perc_dia = linha_dia["perc_dia"]  # já em %
    perc_clamp = max(min(perc_dia, 10), -10)  # limitar entre -10% e 10%

    if perc_clamp >= 2:
        score_resultado = 30
    elif perc_clamp <= -5:
        score_resultado = 0
    else:
        # escala linear entre -5% e 2%
        score_resultado = (perc_clamp + 5) / (2 + 5) * 30  # 0–30

    peso_resultado = 30
    contrib_resultado = (score_resultado / 30) * peso_resultado

    # --- Direção (Candle 9 / 10:15) + Risco ---
    contrib_direcao = 0
    contrib_risco = 0
    ctx_info_text = "Sem contexto de Candle 9 / 10:15 / risco para este dia."

    if df_ctx is not None:
        linha_ctx = df_ctx[df_ctx["data"].dt.date == data_termometro]
        if not linha_ctx.empty:
            ctx = linha_ctx.iloc[0]

            # Direção
            peso_direcao = 20
            if ctx["candle9_dir"] == ctx["candle1015_dir"]:
                score_direcao = 20
            else:
                score_direcao = 10
            contrib_direcao = (score_direcao / 20) * peso_direcao

            # Risco do dia
            peso_risco = 10
            risco_noticias = ctx["risco_noticias"]  # 0–10
            score_risco = (10 - risco_noticias)  # quanto menor o risco, maior score
            contrib_risco = (score_risco / 10) * peso_risco

            ctx_info_text = (
                f"Candle 9: {ctx['candle9_dir']} | "
                f"Candle 10:15: {ctx['candle1015_dir']} | "
                f"Risco notícias: {ctx['risco_noticias']}/10 | "
                f"Payroll: {ctx['dia_de_payroll']} | "
                f"Comentário: {ctx['comentario_dia']}"
            )

    # --- Termômetro Final ---
    termometro = contrib_disciplina + contrib_resultado + contrib_direcao + contrib_risco
    termometro = round(termometro, 1)

    col_t1, col_t2 = st.columns([1, 3])

    with col_t1:
        if termometro < 30:
            status = "❄️ Frio / Perigoso"
        elif termometro < 60:
            status = "😐 Neutro"
        elif termometro < 80:
            status = "🔥 Quente (Bom dia)"
        else:
            status = "🔥🔥 Excelente (Dia redondinho)"

        st.metric("Temperatura do dia", f"{termometro}/100", status)

    with col_t2:
        st.write("Nível do Termômetro")
        st.progress(min(termometro / 100, 1.0))
        st.caption(ctx_info_text)
