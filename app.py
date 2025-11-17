import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO
import matplotlib.pyplot as plt
import altair as alt

# -----------------------------------------------------------------------------
# CONFIG DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Termômetro do Trader",
    page_icon="🌡️",
    layout="wide",
)

BANCA_INICIAL_PADRAO = 200.0
MAX_TRADES_DIA = 5
ALVO_GAIN_DIA = 200.0
MAX_LOSS_DIA = -70.0  # -70 de loss

# -----------------------------------------------------------------------------
# FUNÇÕES DE CARGA
# -----------------------------------------------------------------------------
@st.cache_data
def carregar_trades_arquivo(caminho: str = "trades.csv") -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["data"])
    df = df.sort_values("data")
    return df

@st.cache_data
def carregar_contexto(caminho: str = "contexto_dia.csv") -> pd.DataFrame:
    df_ctx = pd.read_csv(caminho, parse_dates=["data"])
    df_ctx = df_ctx.sort_values("data")
    return df_ctx

# -----------------------------------------------------------------------------
# CARREGAR TRADES (BASE) E INICIAR SESSION_STATE
# -----------------------------------------------------------------------------
try:
    df_base = carregar_trades_arquivo()
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

# garante tipos mínimos
df_base["resultado_r"] = pd.to_numeric(df_base["resultado_r"], errors="coerce").fillna(0.0)
df_base["data"] = pd.to_datetime(df_base["data"])

# session_state: df_trades é a planilha "viva" da sessão
if "df_trades" not in st.session_state:
    st.session_state["df_trades"] = df_base.copy()

df = st.session_state["df_trades"]

# -----------------------------------------------------------------------------
# TÍTULO
# -----------------------------------------------------------------------------
st.title("🌡️ Termômetro do Trader")
st.write("Dashboard de Daytrade com diário do trader, banca, performance, disciplina e contexto de mercado.")

# =============================================================================
# SIDEBAR – DIÁRIO DO TRADER + PIZZA + DOWNLOAD
# =============================================================================

# -----------------------------------------------------------------------------
# FORMULÁRIO DO DIÁRIO DO TRADER
# -----------------------------------------------------------------------------
st.sidebar.header("📓 Diário do Trader - Novo Trade")

# Data do trade (auto hoje, mas editável)
data_trade = st.sidebar.date_input("Data do trade", value=pd.Timestamp.today())

# Ativo com sugestão (último ativo ou WINZ25)
ativo_sugestao = "WINZ25"
if "ativo" in df.columns and not df["ativo"].dropna().empty:
    ativo_sugestao = str(df["ativo"].iloc[-1])

ativo = st.sidebar.text_input("Ativo", value=ativo_sugestao)

# Ponto de entrada / saída
entrada = st.sidebar.number_input("Ponto de entrada", value=0.0, step=5.0, format="%.1f")
saida = st.sidebar.number_input("Ponto de saída", value=0.0, step=5.0, format="%.1f")

# Direção
direcao = st.sidebar.radio("Direção", options=["COMPRA", "VENDA"])

# Número de contratos
num_contratos = st.sidebar.number_input(
    "Número de contratos", min_value=1, value=1, step=1
)

# Quantidade de operações (parciais dentro do mesmo trade)
qtd_operacoes = st.sidebar.number_input(
    "Quantidade de operações", min_value=1, value=1, step=1
)

# Custo por ponto (R$) – mini índice ~0.20
custo_ponto = st.sidebar.number_input(
    "Custo por ponto (R$)", min_value=0.0, value=0.20, step=0.05, format="%.2f"
)

# Setup do dia
setup = st.sidebar.text_input("Setup do dia", value="")

# Motivo da Entrada
motivo_entrada = st.sidebar.text_area("Motivo da entrada", height=80)

# Emocional
emocional = st.sidebar.selectbox(
    "Emocional",
    options=["Calmo", "Confiante", "Neutro", "Ansioso", "Com medo", "Eufórico"],
    index=2,
)

# Seguiu as regras?
seguiu_regras = st.sidebar.checkbox("Segui 100% minhas regras?", value=True)

# Comentários gerais
comentarios = st.sidebar.text_area("Comentários adicionais", height=80)

# --- Cálculo automático de pontos/ticks a partir de entrada/saída ---
if direcao == "COMPRA":
    pontos_por_operacao = saida - entrada
else:  # VENDA
    pontos_por_operacao = entrada - saida

total_pontos = pontos_por_operacao * qtd_operacoes
resultado_estimado = total_pontos * num_contratos * custo_ponto

st.sidebar.markdown(
    f"**Pontos por operação**: `{pontos_por_operacao:.1f}` pts\n\n"
    f"**Total de pontos (gain/loss)**: `{total_pontos:.1f}` pts\n\n"
    f"**Resultado estimado (R$)**: `R$ {resultado_estimado:.2f}`"
)

# -----------------------------------------------------------------------------
# DISCIPLINA BASEADA NAS REGRAS (5 trades, 200 gain, 70 loss)
# -----------------------------------------------------------------------------
def calcular_disciplina(
    seguiu: bool,
    resultado_trade: float,
    trades_hoje: int,
    lucro_dia_novo: float,
    max_trades: int = MAX_TRADES_DIA,
    alvo_gain: float = ALVO_GAIN_DIA,
    max_loss: float = MAX_LOSS_DIA,
) -> int:
    """
    Score começa em 100 e aplica penalidades:
    - Não seguiu regras: -30
    - Excedeu nº máximo de trades no dia: -30
    - Bateu stop de loss diário (<= max_loss): score máximo 30
    - Bateu alvo de gain diário (>= alvo_gain): score máximo 90
    """
    score = 100

    if not seguiu:
        score -= 30

    if trades_hoje > max_trades:
        score -= 30

    # Stop diário de loss
    if lucro_dia_novo <= max_loss:
        score = min(score, 30)

    # Alvo diário de gain
    if lucro_dia_novo >= alvo_gain:
        score = min(score, 90)

    score = max(0, min(100, score))
    return int(round(score))

# Quantos trades já existem neste dia (antes de incluir este)?
df_dia_atual = df[df["data"].dt.date == data_trade]
trades_hoje = df_dia_atual.shape[0] + 1  # contando este trade novo

lucro_dia_atual = df_dia_atual["resultado_r"].sum()
lucro_dia_novo = lucro_dia_atual + resultado_estimado

disciplina_nota = calcular_disciplina(
    seguiu_regras,
    resultado_estimado,
    trades_hoje,
    lucro_dia_novo,
)

st.sidebar.markdown(f"### 🧭 Disciplina calculada: **{disciplina_nota} / 100**")

# Botão para adicionar o trade ao diário (na sessão)
if st.sidebar.button("➕ Adicionar ao diário"):
    nova_linha = {
        "data": pd.to_datetime(data_trade),
        "ativo": ativo,
        "direcao": direcao,
        "setup": setup,
        "entrada": entrada,
        "saida": saida,
        "resultado_r": resultado_estimado,
        "resultado_pts": total_pontos,
        "num_contratos": num_contratos,
        "qtd_operacoes": qtd_operacoes,
        "custo_ponto": custo_ponto,
        "disciplina": disciplina_nota,
        "quebrou_regras": "NAO" if seguiu_regras else "SIM",
        "comentarios": comentarios,
        "motivo_entrada": motivo_entrada,
        "emocional": emocional,
    }

    # garante colunas
    for col in nova_linha.keys():
        if col not in df.columns:
            df[col] = np.nan

    st.session_state["df_trades"] = pd.concat(
        [df, pd.DataFrame([nova_linha])], ignore_index=True
    )
    df = st.session_state["df_trades"]
    st.sidebar.success("Trade adicionado ao diário nesta sessão! ✅")

# -----------------------------------------------------------------------------
# PIZZA DA SEMANA + DOWNLOAD
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Semana (Ganhos x Perdas)")

if df.empty:
    st.sidebar.info("Ainda não há trades cadastrados.")
else:
    ultimo_dia_semana = df["data"].max()
    inicio_semana = ultimo_dia_semana - pd.Timedelta(days=6)

    df_semana = df[
        (df["data"] >= inicio_semana) & (df["data"] <= ultimo_dia_semana)
    ]

    total_ganhos_semana = df_semana.loc[df_semana["resultado_r"] > 0, "resultado_r"].sum()
    total_perdas_semana = df_semana.loc[df_semana["resultado_r"] < 0, "resultado_r"].sum()

    valores_pizza = [max(total_ganhos_semana, 0), abs(min(total_perdas_semana, 0))]
    labels_pizza = ["Ganhos", "Perdas"]

    if sum(valores_pizza) == 0:
        st.sidebar.info("Ainda não há dados suficientes nesta semana para o gráfico.")
    else:
        fig_pizza, ax_pizza = plt.subplots()
        ax_pizza.pie(valores_pizza, labels=labels_pizza, autopct="%1.1f%%", startangle=90)
        ax_pizza.axis("equal")
        st.sidebar.pyplot(fig_pizza)

st.sidebar.markdown("---")
csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)
st.sidebar.download_button(
    label="📥 Baixar trades.csv atualizado",
    data=csv_buffer.getvalue(),
    file_name="trades_atualizado.csv",
    mime="text/csv",
)

# =============================================================================
# PARTE PRINCIPAL – CÁLCULOS E DASHBOARD
# =============================================================================

if df.empty:
    st.info("Nenhum trade para exibir ainda. Registre um trade na lateral.")
    st.stop()

# Vamos usar SEMPRE todos os trades para os cálculos
df_filtrado = df.copy()

banca_inicial = BANCA_INICIAL_PADRAO

# -----------------------------------------------------------------------------
# RESUMO POR DIA (P/ EQUITY E TERMÔMETRO)
# -----------------------------------------------------------------------------
df_dias = df_filtrado.groupby("data", as_index=False).agg(
    lucro_dia=("resultado_r", "sum"),
    qtd_trades=("resultado_r", "count"),
    media_disciplina=("disciplina", "mean")
    if "disciplina" in df_filtrado.columns
    else ("resultado_r", "count"),
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

df_equity = pd.DataFrame(saldos).sort_values("data")

banca_final = df_equity["banca_fim_dia"].iloc[-1]
lucro_total = banca_final - banca_inicial
perc_total = (lucro_total / banca_inicial) * 100 if banca_inicial != 0 else np.nan

# -----------------------------------------------------------------------------
# ESTATÍSTICAS GERAIS
# -----------------------------------------------------------------------------
total_trades = df_filtrado.shape[0]
wins = df_filtrado[df_filtrado["resultado_r"] > 0]
losses = df_filtrado[df_filtrado["resultado_r"] < 0]

qtd_wins = wins.shape[0]
qtd_losses = losses.shape[0]
win_rate = (qtd_wins / total_trades) * 100 if total_trades > 0 else 0.0

dias_positivos = df_dias[df_dias["lucro_dia"] > 0].shape[0]
dias_totais = df_dias.shape[0]
win_rate_dias = (dias_positivos / dias_totais) * 100 if dias_totais > 0 else 0.0

gross_profit = wins["resultado_r"].sum()
gross_loss = losses["resultado_r"].sum()
profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else np.nan

avg_win = wins["resultado_r"].mean() if not wins.empty else 0.0
avg_loss = losses["resultado_r"].mean() if not losses.empty else 0.0
prob_win = qtd_wins / total_trades if total_trades > 0 else 0.0
prob_loss = 1 - prob_win
expectativa_trade = prob_win * avg_win + prob_loss * avg_loss

ultimo_dia = df_equity["data"].iloc[-1]
lucro_ultimo_dia = df_equity["lucro_dia"].iloc[-1]
perc_ultimo_dia = df_equity["perc_dia"].iloc[-1]

mes_ref = ultimo_dia.month
ano_ref = ultimo_dia.year
df_mes = df_equity[
    (df_equity["data"].dt.month == mes_ref) & (df_equity["data"].dt.year == ano_ref)
]
ganho_mes = df_mes["lucro_dia"].sum()

df_ano = df_equity[df_equity["data"].dt.year == ano_ref]
ganho_ano = df_ano["lucro_dia"].sum()

media_disc_total = (
    df_filtrado["disciplina"].mean()
    if "disciplina" in df_filtrado.columns
    else np.nan
)

# -----------------------------------------------------------------------------
# VISÃO GERAL (CARDS)
# -----------------------------------------------------------------------------
st.subheader("📊 Visão Geral")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Banca inicial", f"R$ {banca_inicial:,.2f}")
c2.metric("Banca atual", f"R$ {banca_final:,.2f}", f"{lucro_total:,.2f} R$")
c3.metric("% acumulado", f"{perc_total:,.2f}%")
c4.metric("Total de trades", int(total_trades))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Ganho último dia", f"R$ {lucro_ultimo_dia:,.2f}", f"{perc_ultimo_dia:,.2f}%")
c6.metric("Ganho no mês", f"R$ {ganho_mes:,.2f}")
c7.metric("Ganho no ano", f"R$ {ganho_ano:,.2f}")
pf_txt = f"{profit_factor:,.2f}" if not np.isnan(profit_factor) else "–"
c8.metric("Fator de lucro", pf_txt)

c9, c10, c11, c12 = st.columns(4)
c9.metric("Expectativa por trade", f"R$ {expectativa_trade:,.2f}")
c10.metric("% acerto (trades)", f"{win_rate:,.2f}%", f"{qtd_wins} W / {qtd_losses} L")
c11.metric("% acerto diário", f"{win_rate_dias:,.2f}%", f"{dias_positivos} dias positivos")
disc_txt = f"{media_disc_total:,.1f}" if not np.isnan(media_disc_total) else "–"
c12.metric("Disciplina média (0–100)", disc_txt)

# -----------------------------------------------------------------------------
# GRÁFICOS – BANCA, GAINS/LOSS (verde/vermelho), DISCIPLINA
# -----------------------------------------------------------------------------
st.subheader("📈 Gráficos de evolução")

# 1) Banca total (equity)
equity_series = df_equity.set_index("data")["banca_fim_dia"]

# 2) Gains x Loss trade a trade (com cores)
df_sorted = df_filtrado.sort_values("data").copy()
df_sorted["ganhos"] = df_sorted["resultado_r"].where(df_sorted["resultado_r"] > 0, 0)
df_sorted["perdas"] = df_sorted["resultado_r"].where(df_sorted["resultado_r"] < 0, 0)

g1, g2 = st.columns(2)

with g1:
    st.caption("Banca total (Equity Curve)")
    st.line_chart(equity_series)

with g2:
    st.caption("Ganhos x perdas por trade")
    chart_data = df_sorted.reset_index()[["data", "ganhos", "perdas"]]
    chart = (
        alt.Chart(chart_data)
        .transform_fold(
            ["ganhos", "perdas"], as_=["tipo", "valor"]
        )
        .mark_line()
        .encode(
            x="data:T",
            y="valor:Q",
            color=alt.condition(
                alt.datum.tipo == "ganhos",
                alt.value("green"),
                alt.value("red"),
            ),
            strokeWidth=alt.condition(
                alt.datum.tipo == "ganhos",
                alt.value(3),
                alt.value(1.5),
            ),
        )
    )
    st.altair_chart(chart, use_container_width=True)

# 3) Disciplina média por dia
if "disciplina" in df_filtrado.columns:
    df_disc = df_filtrado.groupby("data", as_index=False).agg(
        disciplina_media=("disciplina", "mean")
    )
    disc_series = df_disc.set_index("data")["disciplina_media"]
else:
    disc_series = None

st.caption("Disciplina média por dia")
if disc_series is not None and not disc_series.empty:
    st.line_chart(disc_series)
else:
    st.info("Ainda não há dados de disciplina suficientes para montar o gráfico.")

# -----------------------------------------------------------------------------
# TABELA RESUMO POR DIA
# -----------------------------------------------------------------------------
st.subheader("🗓️ Resumo por dia (lucro, % e disciplina)")
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
st.subheader("📋 Trades detalhados")
st.dataframe(df_filtrado, use_container_width=True)

# -----------------------------------------------------------------------------
# TERMÔMETRO DO TRADER – SEMPRE NO ÚLTIMO DIA
# -----------------------------------------------------------------------------
data_termometro = df_equity["data"].iloc[-1].date()
st.subheader(f"🌡️ Termômetro do Trader – {data_termometro}")

linha_dia = df_equity[df_equity["data"].dt.date == data_termometro]
if linha_dia.empty:
    st.warning("Não há dados de equity para o dia selecionado no Termômetro.")
else:
    linha_dia = linha_dia.iloc[0]

    disciplina_media_dia = (
        linha_dia["media_disciplina"] if not pd.isna(linha_dia["media_disciplina"]) else 0.0
    )
    # disciplina (peso 40)
    score_disciplina = (disciplina_media_dia / 100) * 40

    # resultado do dia (peso 30)
    perc_dia = linha_dia["perc_dia"]
    perc_clamp = max(min(perc_dia, 10), -10)
    if perc_clamp >= 2:
        score_resultado = 30
    elif perc_clamp <= -5:
        score_resultado = 0
    else:
        score_resultado = (perc_clamp + 5) / (2 + 5) * 30
    contrib_resultado = score_resultado

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

    termometro = score_disciplina + contrib_resultado + contrib_direcao + contrib_risco
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

# -----------------------------------------------------------------------------
# RODAPÉ – REGRAS DO SETUP
# -----------------------------------------------------------------------------
st.markdown("---")
st.caption("setup – **5 trades / dia** • **200 gain** • **70 loss**")
