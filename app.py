import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

TRADES_FILE = "trades.csv"
CONTEXTO_FILE = "contexto_dia.csv"

# -------------------------------
# GARANTIR QUE COLUNAS EXISTEM
# -------------------------------
def ensure_columns():
    required_cols = [
        "data", "ativo", "direcao", "setup", "entrada", "saida",
        "resultado_r", "resultado_pts", "disciplina", "quebrou_regras",
        "comentarios", "num_contratos", "qtd_operacoes", "custo_ponto",
        "motivo_entrada", "emocional"
    ]

    if not os.path.exists(TRADES_FILE):
        df = pd.DataFrame(columns=required_cols)
        df.to_csv(TRADES_FILE, index=False)

    df = pd.read_csv(TRADES_FILE)

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df.to_csv(TRADES_FILE, index=False)


# -------------------------------
# CARREGAR DADOS
# -------------------------------
def load_trades():
    ensure_columns()
    df = pd.read_csv(TRADES_FILE)

    # Converter datas
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    # Preencher padrões
    df["num_contratos"] = df["num_contratos"].fillna(1).astype(int)
    df["qtd_operacoes"] = df["qtd_operacoes"].fillna(1).astype(int)
    df["custo_ponto"] = df["custo_ponto"].fillna(0.20).astype(float)

    # Calcular ticks e resultado
    df["resultado_pts"] = (df["saida"] - df["entrada"]) / 10
    df["resultado_r"] = df["resultado_pts"] * df["custo_ponto"] * df["num_contratos"]

    return df


def save_trades(df):
    df.to_csv(TRADES_FILE, index=False)


# -----------------------------------------------------
# DISCIPLINA
# -----------------------------------------------------
def calcular_disciplina(row):
    if row["quebrou_regras"] == "NAO":
        return 90
    else:
        if row["resultado_r"] > 0:
            return 60
        else:
            return 30


# -----------------------------------------------------
# APP
# -----------------------------------------------------
st.set_page_config(layout="wide")
st.title("🔥 Termômetro do Trader – Dashboard Profissional")

df = load_trades()

# Calcular disciplina atualizada
df["disciplina"] = df.apply(calcular_disciplina, axis=1)

save_trades(df)

# -----------------------------------------------------
# GRÁFICO DE PIZZA – GANHOS X PERDAS
# -----------------------------------------------------
st.subheader("📊 Distribuição de Ganhos e Perdas (Pizza)")

ganhos = df[df["resultado_r"] > 0]["resultado_r"].sum()
perdas = abs(df[df["resultado_r"] < 0]["resultado_r"].sum())

pizza_df = pd.DataFrame({
    "Categoria": ["Ganhos", "Perdas"],
    "Valor": [ganhos, perdas]
})

fig_pizza = px.pie(
    pizza_df,
    names="Categoria",
    values="Valor",
    color="Categoria",
    color_discrete_map={"Ganhos": "green", "Perdas": "red"},
)
st.plotly_chart(fig_pizza, use_container_width=True)

# -----------------------------------------------------
# Gráfico de Linha: Evolução dos resultados
# -----------------------------------------------------
st.subheader("📈 Evolução dos Resultados")

df_sorted = df.sort_values("data")

fig = px.line(
    df_sorted,
    x="data",
    y="resultado_r",
    title="Ganhos x Perdas por trade",
)
fig.update_traces(line=dict(width=4))
fig.update_traces(
    selector=dict(name="resultado_r"),
)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------
# TABELA DETALHADA COM BOTÃO EDITAR
# -----------------------------------------------------
st.subheader("📋 Trades detalhados (com edição)")

for idx, row in df.iterrows():
    with st.expander(f"✏️ Editar Trade ID {idx} — {row['data'].date()} ({row['ativo']})"):

        novo_resultado = {}

        for col in ["data","ativo","direcao","setup","entrada","saida",
                    "quebrou_regras","comentarios","num_contratos",
                    "qtd_operacoes","custo_ponto","motivo_entrada","emocional"]:

            novo_resultado[col] = st.text_input(f"{col}", value=str(row[col]), key=f"{col}_{idx}")

        if st.button(f"Salvar alterações ID {idx}"):
            for c in novo_resultado:
                try:
                    if c in ["entrada","saida","num_contratos","qtd_operacoes"]:
                        df.at[idx, c] = int(novo_resultado[c])
                    elif c == "custo_ponto":
                        df.at[idx, c] = float(novo_resultado[c])
                    elif c == "data":
                        df.at[idx, c] = pd.to_datetime(novo_resultado[c])
                    else:
                        df.at[idx, c] = novo_resultado[c]
                except:
                    pass

            save_trades(df)
            st.success("Alterações salvas!")
            st.rerun()

st.dataframe(df)

# -----------------------------------------------------
# RESET TOTAL
# -----------------------------------------------------
st.subheader("🧹 Resetar Sistema")

confirm = st.checkbox("Sim, desejo apagar TODOS os dados (irreversível)")

if st.button("Apagar tudo", type="primary"):
    if confirm:
        pd.DataFrame().to_csv(TRADES_FILE, index=False)
        pd.DataFrame().to_csv(CONTEXTO_FILE, index=False)
        st.success("Sistema resetado!")
        st.rerun()
    else:
        st.error("Marque a caixa antes de apagar.")

# -----------------------------------------------------
# RODAPÉ
# -----------------------------------------------------
st.markdown("---")
st.markdown("### 📝 Metas do Setup")
st.markdown("""
**• 5 trades por dia**  
**• 200 pontos Gain**  
**• 70 pontos Loss**  
""")

