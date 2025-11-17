import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------------------------------------------------------
# CONFIG BÁSICA DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Termômetro do Trader",
    page_icon="🌡️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .big-metric {
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }
    .sub-metric {
        font-size: 0.9rem !important;
        color: #666666 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌡️ Termômetro do Trader")
st.write("Dashboard de Daytrade: banca, performance, disciplina e contexto de mercado (Candle 9 / 10:15).")

# -----------------------------------------------------------------------------
# FUNÇÕES DE CARGA
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# CARREGANDO DADOS
# -----------------------------------------------------------------------------
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

# Garante tipos mínimos
if "resultado_r" not in df.columns:
    st.error("A coluna 'resultado_r' não existe no trades.csv.")
    st.stop()

df["resultado_r"] = pd.to_numeric(df["resultado_r"], errors="coerce").fillna(0.0)
df["data"] = pd.to_datetime(df["data"])

# -----------------------------------------------------------------------------
# SIDEBAR – CONFIG E FILTROS
# -----------------------------------------------------------------------------
st.sidebar.header("Configuração da Banca e Filtros")

banca_inicial = st.sidebar.number_input(
    "Banca inicial (R$)", min_value=0.0, value=200.0, step=50.0
)

datas_disponiveis = df["data"].dt.date.unique()
datas_disponiveis = np.sort(datas_disponiveis)

if len(datas_disponiveis) == 0:
    st.info("Nenhum dado em trades.csv.")
    st.stop()

data_inicial = st.sidebar.date_input(
    "Data inicial (filtro trades)",
    value=datas_disponiveis[0],
)
data_final = st.sidebar.date_input(
    "Data final (filtro trades)",
    value=datas_disponiveis[-1],
)

ativo_filtro = st.sidebar.text_input("Filtrar por ativo (ex: WIN)", value="")

data_termometro = st.sidebar.selectbox(
    "Dia para análise do Termômetro",
    options=datas_disponiveis,
    index=len(datas_disponiveis) - 1,
)

# -----------------------------------------------------------------------------
# FILTRAR TRADES
# -----------------------------------------------------------------------------
df_filtrado = df.copy()

if data_inicial:
    df_filtrado = df_filtrado[df_filtrado["data"].dt.date >= data_inicial]
if data_final:
    df_filtrado = df_filtrado[df_filtrado["data"].dt.date <= data_final]
if ativo_filtro.strip():
    df_filtrado = df_filtrado[
        df_filtrado["ativo"].astype(str).str.contains(ativo_filtro.strip(), case=False)
    ]

if df_filtrado.empty:
    st.info("Nenhum trade encontrado com os filtros atuais.")
    st.stop()

# -----------------------------------------------------------------------------
# RESUMO POR DIA (P/ EQUITY E TERMÔMETRO)
# -----------------------------------------------------------------------------
df_dias = df_filtrado.groupby("data", as_index=False).agg(
    lucro_dia=("resultado_r", "sum"),
    qtd_trades=("resultado_r", "count"),
    media_disciplina=("disciplina", "mean") if "disciplina" in df_filtrado.columns else ("resultado_r", "count"),
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
df_equity = df_equity.sort_values("data")

banca_final = df_equity["banca_fim_dia"].iloc[-1]
lucro_total = banca_final - banca_inicial
perc_total = (lucro_total / banca_inicial) * 100 if banca_inicial != 0 else np.nan

# -----------------------------------------------------------------------------
# ESTATÍSTICAS DE DAYTRADE (estilo Trademetria)
# -----------------------------------------------------------------------------
total_trades = df_filtrado.shape[0]
wins = df_filtrado[df_filtrado["resultado_r"] > 0]
losses = df_filtrado[df_filtrado["resultado_r"] < 0]

qtd_wins = wins.shape[0]
qtd_losses = losses.shape[0]

win_rate = (qtd_wins / total_trades) * 100 if total_trades > 0 else 0.0

# % de acerto diário (dias positivos)
dias_positivos = df_dias[df_dias["lucro_dia"] > 0].shape[0]
dias_totais = df_dias.shape[0]
win_rate_dias = (dias_positivos / dias_totais) * 100 if dias_totais > 0 else 0.0

# Fator de lucro
gross_profit = wins["resultado_r"].sum()
gross_loss = losses["resultado_r"].sum()  # negativo
profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else np.nan

# Expectativa por trade
avg_win = wins["resultado_r"].mean() if not wins.empty else 0.0
avg_loss = losses["resultado_r"].mean() if not losses.empty else 0.0  # negativo
prob_win = qtd_wins / total_trades if total_trades > 0 else 0.0
prob_loss = 1 - prob_win

expectativa_trade = prob_win * avg_win + prob_loss * avg_loss

# Último dia (ganho do dia)
ultimo_dia = df_equity["data"].iloc[-1]
lucro_ultimo_dia = df_equity["lucro_dia"].iloc[-1]
perc_ultimo_dia = df_equity["perc_dia"].iloc[-1]

# Ganho no mês (mês do último dia filtrado)
mes_ref = ultimo_dia.month
ano_ref = ultimo_dia.year
df_mes = df_equity[
    (df_equity["data"].dt.month == mes_ref) & (df_equity["data"].dt.year == ano_ref)
]
ganho_mes = df_mes["lucro_dia"].sum()

# Ganho no ano
df_ano = df_equity[df_equity["data"].dt.year == ano_ref]
ganho_ano = df_ano["lucro_dia"].sum()

# Ativo mais operado / mais lucrativo
ativo_mais_op = (
    df_filtrado["ativo"].value_counts().index[0]
    if "ativo" in df_filtrado.columns and not df_filtrado["ativo"].value_counts().empty
    else "-"
)
ativo_lucro = "-"
if "ativo" in df_filtrado.columns:
    lucro_por_ativo = df_filtrado.groupby("ativo")["resultado_r"].sum().sort_values(ascending=False)
    if not lucro_por_ativo.empty:
        ativo_lucro = f"{lucro_por_ativo.index[0]} (R$ {lucro_por_ativo.iloc[0]:.2f})"

# -----------------------------------------------------------------------------
# DASHBOARD PRINCIPAL – CARDS
# -----------------------------------------------------------------------------
st.markdown("### 📊 Visão Geral do Daytrade")

row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)

with row1_col1:
    st.markdown("**Saldo (banca atual)**")
    st.markdown(f"<div class='big-metric'>R$ {banca_final:,.2f}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='sub-metric'>Início: R$ {banca_inicial:,.2f} &nbsp; | &nbsp; Δ R$ {lucro_total:,.2f}</div>",
        unsafe_allow_html=True,
    )

with row1_col2:
    st.markdown("**Ganho último dia**")
    st.markdown(f"<div class='big-metric'>R$ {lucro_ultimo_dia:,.2f}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='sub-metric'>{perc_ultimo_dia:,.2f}% sobre a banca do dia</div>",
        unsafe_allow_html=True,
    )

with row1_col3:
    st.markdown("**Ganhos no mês**")
    st.markdown(f"<div class='big-metric'>R$ {ganho_mes:,.2f}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='sub-metric'>Referência: {mes_ref:02d}/{ano_ref}</div>",
        unsafe_allow_html=True,
    )

with row1_col4:
    st.markdown("**Ganhos no ano**")
    st.markdown(f"<div class='big-metric'>R$ {ganho_ano:,.2f}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='sub-metric'>Ano: {ano_ref}</div>",
        unsafe_allow_html=True,
    )

row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)

with row2_col1:
    st.markdown("**Fator de lucro (liq/bruto)**")
    if not np.isnan(profit_factor):
        st.markdown(
            f"<div class='big-metric'>{profit_factor:,.2f}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='big-metric'>–</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-metric'>Bom &gt; 1.5</div>", unsafe_allow_html=True)

with row2_col2:
    st.markdown("**Expectativa por trade**")
    st.markdown(
        f"<div class='big-metric'>R$ {expectativa_trade:,.2f}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='sub-metric'>Valor médio esperado por operação</div>", unsafe_allow_html=True)

with row2_col3:
    st.markdown("**% de acerto (trades)**")
    st.markdown(
        f"<div class='big-metric'>{win_rate:,.2f}%</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='sub-metric'>{qtd_wins} W  /  {qtd_losses} L  (total {total_trades})</div>",
        unsafe_allow_html=True,
    )

with row2_col4:
    st.markdown("**% de acerto diário**")
    st.markdown(
        f"<div class='big-metric'>{win_rate_dias:,.2f}%</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='sub-metric'>{dias_positivos} dias positivos / {dias_totais} dias</div>",
        unsafe_allow_html=True,
    )

# Info de ativos
st.markdown("### 🎯 Ativos operados")
col_a1, col_a2 = st.columns(2)
with col_a1:
    st.markdown("**Ativo mais operado**")
    st.markdown(f"<div class='big-metric'>{ativo_mais_op}</div>", unsafe_allow_html=True)
with col_a2:
    st.markdown("**Ativo mais lucrativo**")
    st.markdown(f"<div class='big-metric'>{ativo_lucro}</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# GRÁFICOS – Banca e Lucro Diário
# -----------------------------------------------------------------------------
st.markdown("### 📈 Evolução da banca e do resultado diário")

g_col1, g_col2 = st.columns(2)

with g_col1:
    st.subheader("Evolução da Banca (Equity Curve)")
    st.area_chart(df_equity.set_index("data")["banca_fim_dia"])

with g_col2:
    st.subheader("Lucro por Dia")
    st.bar_chart(df_equity.set_index("data")["lucro_dia"])

# -----------------------------------------------------------------------------
# TABELA RESUMO POR DIA
# -----------------------------------------------------------------------------
st.markdown("### 🗓️ Resumo por dia (lucro, % e disciplina)")
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

# -----------------------------------------------------------------------------
# TRADES DETALHADOS
# -----------------------------------------------------------------------------
st.markdown("### 📋 Trades detalhados (após filtros)")
st.dataframe(df_filtrado, use_container_width=True)

# -----------------------------------------------------------------------------
# TERMÔMETRO DO TRADER – DIA ESPECÍFICO
# -----------------------------------------------------------------------------
st.markdown(f"### 🌡️ Termômetro do Trader – {data_termometro}")

linha_dia = df_equity[df_equity["data"].dt.date == data_termometro]
if linha_dia.empty:
    st.warning("Não há dados de equity para o dia selecionado no Termômetro.")
else:
    linha_dia = linha_dia.iloc[0]

    # Disciplina
    disciplina_media = linha_dia["media_disciplina"] if "media_disciplina" in linha_dia else np.nan
    if pd.isna(disciplina_media):
        disciplina_media = 0.0
    score_disciplina = disciplina_media * 10
    peso_disciplina = 40
    contrib_disciplina = (score_disciplina / 100) * peso_disciplina

    # Resultado do dia
    perc_dia = linha_dia["perc_dia"]  # %
    perc_clamp = max(min(perc_dia, 10), -10)

    if perc_clamp >= 2:
        score_resultado = 30
    elif perc_clamp <= -5:
        score_resultado = 0
    else:
        score_resultado = (perc_clamp + 5) / (2 + 5) * 30

    peso_resultado = 30
    contrib_resultado = (score_resultado / 30) * peso_resultado

    # Direção + risco
    contrib_direcao = 0
    contrib_risco = 0
    ctx_info_text = "Sem contexto de Candle 9 / 10:15 / risco para este dia."

    if df_ctx is not None:
        linha_ctx = df_ctx[df_ctx["data"].dt.date == data_termometro]
        if not linha_ctx.empty:
            ctx = linha_ctx.iloc[0]

            peso_direcao = 20
            if ctx["candle9_dir"] == ctx["candle1015_dir"]:
                score_direcao = 20
            else:
                score_direcao = 10
            contrib_direcao = (score_direcao / 20) * peso_direcao

            peso_risco = 10
            risco_noticias = ctx["risco_noticias"]
            score_risco = (10 - risco_noticias)
            contrib_risco = (score_risco / 10) * peso_risco

            ctx_info_text = (
                f"Candle 9: {ctx['candle9_dir']} | "
                f"Candle 10:15: {ctx['candle1015_dir']} | "
                f"Risco notícias: {ctx['risco_noticias']}/10 | "
                f"Payroll: {ctx['dia_de_payroll']} | "
                f"Comentário: {ctx['comentario_dia']}"
            )

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
