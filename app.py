#import streamlit as st
#import pandas as pd
#import numpy as np
#from io import StringIO
import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO
import matplotlib.pyplot as plt  # <-- ADICIONA ESTA LINHA


# -----------------------------------------------------------------------------
# CONFIG DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Termômetro do Trader",
    page_icon="🌡️",
    layout="wide",
)

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
st.write("Dashboard de Daytrade com diário do trader, banca, performance e contexto de mercado.")

# -----------------------------------------------------------------------------
# SIDEBAR – DIÁRIO DO TRADER + FILTROS
# -----------------------------------------------------------------------------
st.sidebar.header("📓 Diário do Trader - Novo Trade")

# Data (auto hoje, mas editável)
data_trade = st.sidebar.date_input("Data do trade")

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

# Setup do dia
setup = st.sidebar.text_input("Setup do dia", value="")

# Motivo da Entrada
motivo_entrada = st.sidebar.text_area("Motivo da entrada", height=80)

# Resultado (R$)
resultado_r = st.sidebar.number_input("Resultado (R$)", value=0.0, step=5.0, format="%.2f")

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

# Função para calcular disciplina
def calcular_disciplina(seguiu: bool, resultado: float) -> int:
    """
    Regras que você descreveu:
    - Se seguir as regras e ficar positivo: 71 a 100 (vamos usar 90)
    - Se seguir as regras e ficar negativo: ainda disciplinado (vamos usar 80)
    - Se NÃO seguir as regras e ficar positivo: 41 a 70 (vamos usar 60)
    - Se NÃO seguir as regras e ficar negativo: 0 a 40 (vamos usar 30)
    """
    if seguiu:
        if resultado >= 0:
            return 90
        else:
            return 80
    else:
        if resultado >= 0:
            return 60
        else:
            return 30

# Botão para adicionar o trade ao diário
if st.sidebar.button("➕ Adicionar ao diário"):
    # calcula resultado em pontos (bem simples: saída - entrada, ajusta para compra/venda)
    if direcao == "COMPRA":
        resultado_pts = saida - entrada
    else:
        resultado_pts = entrada - saida

    disciplina_nota = calcular_disciplina(seguiu_regras, resultado_r)
    quebrou_regras = "NAO" if seguiu_regras else "SIM"

    nova_linha = {
        "data": pd.to_datetime(data_trade),
        "ativo": ativo,
        "direcao": direcao,
        "setup": setup,
        "entrada": entrada,
        "saida": saida,
        "resultado_r": resultado_r,
        "resultado_pts": resultado_pts,
        "disciplina": disciplina_nota,
        "quebrou_regras": quebrou_regras,
        "comentarios": comentarios,
        "motivo_entrada": motivo_entrada,
        "emocional": emocional,
    }

    # garante que todas as colunas existem
    for col in nova_linha.keys():
        if col not in df.columns:
            df[col] = np.nan

    st.session_state["df_trades"] = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
    df = st.session_state["df_trades"]
    st.sidebar.success("Trade adicionado ao diário na sessão atual! ✅")

# Separador na sidebar para filtros
st.sidebar.markdown("---")
st.sidebar.header("Filtros de visualização")

banca_inicial = st.sidebar.number_input(
    "Banca inicial (R$)", min_value=0.0, value=200.0, step=50.0
)

datas_disponiveis = df["data"].dt.date.unique()
datas_disponiveis = np.sort(datas_disponiveis)

if len(datas_disponiveis) == 0:
    st.info("Nenhum dado em trades (nem da planilha e nem do diário).")
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

# Botão para baixar CSV atualizado (diário + base)
st.sidebar.markdown("---")
csv_buffer = StringIO()
df.to_csv(csv_buffer, index=False)
st.sidebar.download_button(
    label="📥 Baixar trades.csv atualizado",
    data=csv_buffer.getvalue(),
    file_name="trades_atualizado.csv",
    mime="text/csv",
)

# -----------------------------------------------------------------------------
# APLICAR FILTROS NOS TRADES
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
# ESTATÍSTICAS GERAIS
# -----------------------------------------------------------------------------
total_trades = df_filtrado.shape[0]
wins = df_filtrado[df_filtrado["resultado_r"] > 0]
losses = df_filtrado[df_filtrado["resultado_r"] < 0]

qtd_wins = wins.shape[0]
qtd_losses = losses.shape[0]

win_rate = (qtd_wins / total_trades) * 100 if total_trades > 0 else 0.0

# % acerto diário
dias_positivos = df_dias[df_dias["lucro_dia"] > 0].shape[0]
dias_totais = df_dias.shape[0]
win_rate_dias = (dias_positivos / dias_totais) * 100 if dias_totais > 0 else 0.0

# Fator de lucro
gross_profit = wins["resultado_r"].sum()
gross_loss = losses["resultado_r"].sum()
profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else np.nan

# Expectativa por trade
avg_win = wins["resultado_r"].mean() if not wins.empty else 0.0
avg_loss = losses["resultado_r"].mean() if not losses.empty else 0.0
prob_win = qtd_wins / total_trades if total_trades > 0 else 0.0
prob_loss = 1 - prob_win
expectativa_trade = prob_win * avg_win + prob_loss * avg_loss

# Último dia / mês / ano
ultimo_dia = df_equity["data"].iloc[-1]
lucro_ultimo_dia = df_equity["lucro_dia"].iloc[-1]
perc_ultimo_dia = df_equity["perc_dia"].iloc[-1]

mes_ref = ultimo_dia.month
ano_ref = ultimo_dia.year
df_mes = df_equity[(df_equity["data"].dt.month == mes_ref) & (df_equity["data"].dt.year == ano_ref)]
ganho_mes = df_mes["lucro_dia"].sum()

df_ano = df_equity[df_equity["data"].dt.year == ano_ref]
ganho_ano = df_ano["lucro_dia"].sum()

# -----------------------------------------------------------------------------
# VISÃO GERAL (CARDS SIMPLES)
# -----------------------------------------------------------------------------
st.subheader("📊 Visão Geral")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Banca inicial", f"R$ {banca_inicial:,.2f}")
c2.metric("Banca atual", f"R$ {banca_final:,.2f}", f"{lucro_total:,.2f} R$")
c3.metric("% acumulado", f"{perc_total:,.2f}%")
c4.metric("Total de trades (filtro)", int(total_trades))

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
media_disc_total = df_filtrado["disciplina"].mean() if "disciplina" in df_filtrado.columns else np.nan
disc_txt = f"{media_disc_total:,.1f}" if not np.isnan(media_disc_total) else "–"
c12.metric("Disciplina média (trades)", disc_txt)

# -----------------------------------------------------------------------------
# GRÁFICOS
# -----------------------------------------------------------------------------
st.subheader("📈 Evolução da banca e do resultado diário")
g1, g2 = st.columns(2)

with g1:
    st.caption("Equity Curve (banca ao final de cada dia)")
    st.line_chart(df_equity.set_index("data")["banca_fim_dia"])

with g2:
    st.caption("Lucro por dia (R$)")
    st.bar_chart(df_equity.set_index("data")["lucro_dia"])

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
st.subheader("📋 Trades detalhados (após filtros)")
st.dataframe(df_filtrado, use_container_width=True)

# -----------------------------------------------------------------------------
# TERMÔMETRO DO TRADER – DIA ESPECÍFICO
# -----------------------------------------------------------------------------
st.subheader(f"🌡️ Termômetro do Trader – {data_termometro}")

linha_dia = df_equity[df_equity["data"].dt.date == data_termometro]
if linha_dia.empty:
    st.warning("Não há dados de equity para o dia selecionado no Termômetro.")
else:
    linha_dia = linha_dia.iloc[0]

    disciplina_media = linha_dia["media_disciplina"] if not pd.isna(linha_dia["media_disciplina"]) else 0.0
    score_disciplina = disciplina_media * 10 / 100 * 40  # normaliza para peso 40

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
