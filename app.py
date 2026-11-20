# Painel de Desempenho Escolar - versão final (AC4)
import io
import re
import streamlit as st
import pandas as pd
import os
import datetime
import streamlit.components.v1 as components
from controle.db import (
    inicializar_banco, 
    buscar_periodos, 
    buscar_turmas,
    buscar_disciplinas,
    buscar_turmas_por_periodo, 
    buscar_alunos_por_turma, 
    buscar_alunos_da_turma_por_id,
    buscar_notas_aluno_com_ids,
    verificar_nota_existente,
    atualizar_nota_por_id,
    deletar_nota_por_id,
    obter_conexao, 
    deletar_banco,
    buscar_media_por_disciplina,
    buscar_resumo_turma,
    buscar_alunos_abaixo_media,
    buscar_medias_disciplina_por_trimestre,
    buscar_resumo_turma_por_trimestre,
    buscar_alunos_da_turma_por_nome,
    buscar_notas_aluno_por_trimestre,
    buscar_turmas_com_resumo,
    contar_alunos_em_comum,
    renomear_ou_unir_turma,
    buscar_base_analise,
    DB_PATH
)

st.set_page_config(page_title="Painel de Desempenho Escolar", layout="wide")

st.title("Painel de Desempenho Escolar")

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro ao inicializar o banco de dados: {e}")

if "params_avaliacao" not in st.session_state:
    st.session_state.params_avaliacao = {
        "max_parcial": 3.0,
        "max_diversificada": 3.0,
        "max_trimestral": 4.0,
        "peso_1": 1,
        "peso_2": 2,
        "peso_3": 3,
        "media_minima": 6.0,
        "configurado": False
    }

# Garante os campos de peso caso a sessão tenha sido criada por uma versão anterior
for chave, padrao in [("peso_1", 1), ("peso_2", 2), ("peso_3", 3), ("media_minima", 6.0)]:
    st.session_state.params_avaliacao.setdefault(chave, padrao)

if "importacao_pendente" not in st.session_state:
    st.session_state.importacao_pendente = None

menu_principal = st.radio(
    "Módulo Principal:", 
    ["Consulta", "Análises e Gráficos", "Cadastro"], 
    horizontal=True
)

st.markdown("---")

def validar_e_calcular_notas(p, d, t):
    erros = []
    cfg = st.session_state.params_avaliacao
    
    max_p = cfg["max_parcial"]
    max_d = cfg["max_diversificada"]
    max_t = cfg["max_trimestral"]
    
    if p < 0:
        erros.append("Nota Parcial não pode ser negativa.")
    elif p > max_p:
        erros.append(f"Nota Parcial ({p:.1f}) excede o máximo permitido ({max_p:.1f}).")
        
    if d < 0:
        erros.append("Nota Diversificada não pode ser negativa.")
    elif d > max_d:
        erros.append(f"Nota Diversificada ({d:.1f}) excede o máximo permitido ({max_d:.1f}).")
        
    if t < 0:
        erros.append("Nota Trimestral não pode ser negativa.")
    elif t > max_t:
        erros.append(f"Nota Trimestral ({t:.1f}) excede o máximo permitido ({max_t:.1f}).")
        
    nota_final = round(p + d + t, 1)
        
    if nota_final < 0:
        erros.append("A Nota Final resultante não pode ser negativa.")
    if nota_final > 10.0:
        erros.append(f"A Nota Final resultante ({nota_final:.1f}) ultrapassa o limite máximo de 10.0.")
        
    return nota_final, erros

# Calcula a altura da tabela para exibir todas as linhas sem barra de rolagem
def altura_tabela(df):
    return 35 * (len(df) + 1) + 3

# Retorna o peso do trimestre a partir do nome do período (ex: "2º TRIMESTRE" -> peso_2)
def peso_do_periodo(periodo):
    cfg = st.session_state.params_avaliacao
    numero = periodo.strip()[0]
    return cfg.get(f"peso_{numero}", 1)

# Calcula pontos, média e situação de uma disciplina a partir das notas dos trimestres
# Média Final = (1º x peso 1 + 2º x peso 2 + 3º x peso 3) / soma dos pesos
def calcular_media_final(notas_por_periodo):
    cfg = st.session_state.params_avaliacao
    soma_pesos = cfg["peso_1"] + cfg["peso_2"] + cfg["peso_3"]
    pontos_minimos = cfg["media_minima"] * soma_pesos
    
    pontos = 0.0
    trimestres_lancados = []
    for periodo, nota in notas_por_periodo.items():
        if pd.notnull(nota):
            pontos += float(nota) * peso_do_periodo(periodo)
            trimestres_lancados.append(periodo.strip()[0])
    
    trimestres_restantes = [n for n in ["1", "2", "3"] if n not in trimestres_lancados]
    pesos_lancados = sum(cfg[f"peso_{n}"] for n in trimestres_lancados)
    pesos_restantes = sum(cfg[f"peso_{n}"] for n in trimestres_restantes)
    
    pontos = round(pontos, 1)
    pontos_faltantes = round(max(pontos_minimos - pontos, 0.0), 1)
    
    if not trimestres_restantes:
        # Ano completo: média final oficial
        media = round(pontos / soma_pesos, 1)
        situacao = "Atingiu a média" if pontos >= pontos_minimos else "Abaixo da média"
    else:
        # Ano em andamento: média ponderada só dos trimestres já lançados
        media = round(pontos / pesos_lancados, 1) if pesos_lancados > 0 else 0.0
        nomes_restantes = " e ".join(f"{n}º" for n in trimestres_restantes)
        if pontos >= pontos_minimos:
            situacao = "Já atingiu a média"
        else:
            nota_necessaria = pontos_faltantes / pesos_restantes
            if nota_necessaria > 10:
                situacao = "Não atinge mais a média"
            else:
                situacao = f"Precisa de média {nota_necessaria:.1f} no {nomes_restantes} trimestre"
    
    return pontos, media, pontos_faltantes, situacao, len(trimestres_restantes) == 0

# Cores dos gráficos (tons de azul e cores neutras, sem verde)
CORES_GRAFICOS = ["#1f4e79", "#4a90d9", "#9ecae1", "#d9822b", "#7f7f7f", "#a83232", "#6a3d9a", "#c49c00", "#0b2545", "#e0a96d"]

def cores_para(qtd):
    """Retorna uma lista de cores com a quantidade de séries do gráfico."""
    return [CORES_GRAFICOS[i % len(CORES_GRAFICOS)] for i in range(qtd)]

def extrair_serie(nome_turma):
    """Obtém a série a partir do nome da turma (ex: "2 SÉRIE B" -> "2ª SÉRIE")."""
    m = re.match(r'^\s*(\d+)\s*[ªº°]?\s*(S[ÉE]RIE|ANO)', str(nome_turma), flags=re.IGNORECASE)
    if m:
        return f"{m.group(1)}ª {m.group(2).upper()}" if m.group(2).upper() != "ANO" else f"{m.group(1)}º ANO"
    partes = str(nome_turma).rsplit(" ", 1)
    return partes[0] if len(partes) > 1 else str(nome_turma)

def centralizar(df, config=None):
    """
    Monta o column_config da tabela deixando as colunas numéricas centralizadas.
    Mantém as configurações já informadas (rótulo, formato) e só acrescenta o alinhamento.
    """
    config = dict(config or {})
    for coluna in df.columns:
        serie = df[coluna]
        if pd.api.types.is_numeric_dtype(serie):
            numerica = True
        else:
            texto = serie.dropna().astype(str).str.replace(',', '.').str.strip()
            numerica = len(texto) > 0 and texto.str.match(r'^[-+]?\d+(\.\d+)?$').all()
        if not numerica:
            continue
        if coluna in config and isinstance(config[coluna], dict):
            config[coluna] = {**config[coluna], "alignment": "center"}
        elif pd.api.types.is_float_dtype(serie):
            formato = "%+.1f" if "Variação" in str(coluna) else "%.1f"
            config[coluna] = st.column_config.NumberColumn(str(coluna), format=formato, alignment="center")
        else:
            config[coluna] = st.column_config.Column(str(coluna), alignment="center")
    return config

def tabela_centralizada(df, **kwargs):
    """Exibe a tabela ajustada ao conteúdo e centralizada na tela."""
    with st.container(horizontal_alignment="center"):
        st.dataframe(df, **kwargs)

def resumir_notas(df, colunas_grupo, nota_corte):
    """Agrupa as notas e calcula média, quantidade de alunos e percentual de notas abaixo do corte."""
    resumo = df.groupby(colunas_grupo).agg(
        MEDIA=('NOTA_FINAL', 'mean'),
        ALUNOS=('ALUNO_ID', 'nunique'),
        NOTAS=('NOTA_FINAL', 'count'),
        ABAIXO=('NOTA_FINAL', lambda x: (x < nota_corte).sum())
    ).reset_index()
    resumo['MEDIA'] = resumo['MEDIA'].round(1)
    resumo['PERC_ABAIXO'] = (resumo['ABAIXO'] / resumo['NOTAS'] * 100).round(0)
    return resumo

def processar_valor_celula(valor, campo_nome):
    if pd.isna(valor) or str(valor).strip() == "":
        return 0.0, False, None
    
    val_str = str(valor).strip()
    
    if isinstance(valor, (datetime.datetime, datetime.date, pd.Timestamp)) or ('-' in val_str and ':' in val_str) or val_str.startswith('2026-'):
        return 0.0, True, f"{campo_nome}: formato data/hora ('{val_str}')"
    
    val_clean = val_str.replace(',', '.')
    try:
        return round(float(val_clean), 1), False, None
    except:
        return 0.0, True, f"{campo_nome}: valor inválido ('{valor}')"

# =========================================================================
# MÓDULO 1: CONSULTA DE ALUNOS (Com Visão AC3)
# =========================================================================
if menu_principal == "Consulta":
    st.subheader("Consulta de Desempenho e Análise")
    
    if os.path.exists(DB_PATH):
        try:
            df_periodos = buscar_periodos()
            
            if not df_periodos.empty:
                lista_periodos = ["Selecione..."] + list(df_periodos['periodo'])
                periodo_selecionado = st.selectbox("Período Letivo:", lista_periodos)
                
                if periodo_selecionado != "Selecione...":
                    df_turmas = buscar_turmas_por_periodo(periodo_selecionado)
                    
                    if not df_turmas.empty:
                        lista_turmas = ["Selecione..."] + list(df_turmas['nome_turma'])
                        turma_selecionada = st.selectbox("Turma:", lista_turmas)
                        
                        if turma_selecionada != "Selecione...":
                            tipo_consulta = st.radio(
                                "Visão de Consulta:", 
                                ["Panorama Geral e Média da Turma", "Comparativo entre Trimestres", "Boletim Individual do Aluno"],
                                horizontal=True
                            )
                            st.markdown("---")
                            
                            if tipo_consulta == "Panorama Geral e Média da Turma":
                                st.markdown(f"#### Média da Sala por Componente Curricular - Turma: {turma_selecionada}")
                                df_medias_disc = buscar_media_por_disciplina(periodo_selecionado, turma_selecionada)
                                
                                if not df_medias_disc.empty:
                                    df_medias_exibicao = df_medias_disc.rename(columns={
                                        'DISCIPLINA': 'Componente Curricular',
                                        'MEDIA_TURMA': 'Média Geral da Turma',
                                        'TOTAL_AVALIADOS': 'Total de Alunos Avaliados'
                                    })
                                    tabela_centralizada(df_medias_exibicao, width="content", hide_index=True, height=altura_tabela(df_medias_exibicao), column_config=centralizar(df_medias_exibicao))

                                    
                                    # Alunos com nota abaixo da nota de corte (AC3)
                                    st.markdown("---")
                                    st.markdown("##### Alunos com Nota Abaixo da Média")
                                    nota_corte = st.number_input(
                                        "Nota de corte geral (vale para todas as disciplinas):",
                                        min_value=0.0, max_value=10.0,
                                        value=float(st.session_state.params_avaliacao.get("media_minima", 6.0)),
                                        step=0.5, format="%.1f",
                                        help="É um único valor, igual para todas as disciplinas. Não existe uma nota de corte diferente por disciplina."
                                    )
                                    st.caption(
                                        f"A nota de corte é a mesma para todas as disciplinas. Ela é usada de duas formas: "
                                        f"**(1)** uma disciplina fica abaixo quando a nota final do aluno nela é menor que {nota_corte:.1f}; "
                                        f"**(2)** a média do aluno é a média de todas as suas disciplinas no trimestre, comparada com {nota_corte:.1f}."
                                    )
                                    
                                    df_resumo = buscar_resumo_turma(periodo_selecionado, turma_selecionada)
                                    df_abaixo = buscar_alunos_abaixo_media(periodo_selecionado, turma_selecionada, nota_corte)
                                    
                                    total_alunos = int(df_resumo['TOTAL_ALUNOS'].iloc[0])
                                    media_geral = float(df_resumo['MEDIA_GERAL'].iloc[0] or 0.0)
                                    qtd_com_disciplina_abaixo = len(df_abaixo)
                                    qtd_media_abaixo = int((df_abaixo['MEDIA_ALUNO'] < nota_corte).sum()) if not df_abaixo.empty else 0
                                    perc_media_abaixo = (qtd_media_abaixo / total_alunos * 100) if total_alunos > 0 else 0.0
                                    
                                    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                                    c_m1.metric("Média Geral da Turma", f"{media_geral:.1f}")
                                    c_m2.metric("Total de Alunos", total_alunos)
                                    c_m3.metric("Alunos com Média Geral Abaixo do Corte", f"{qtd_media_abaixo} ({perc_media_abaixo:.0f}%)")
                                    c_m4.metric("Alunos com 1 ou mais Disciplinas Abaixo", qtd_com_disciplina_abaixo)
                                    
                                    if not df_abaixo.empty:
                                        df_abaixo_exibicao = df_abaixo.rename(columns={
                                            'CHAMADA': 'Nº',
                                            'ALUNO': 'Aluno',
                                            'MEDIA_ALUNO': 'Média do Aluno',
                                            'QTD_DISCIPLINAS': 'Qtd. Disciplinas Abaixo',
                                            'DISCIPLINAS': 'Disciplinas Abaixo do Corte',
                                            'MENOR_NOTA': 'Menor Nota'
                                        })
                                        tabela_centralizada(
                                            df_abaixo_exibicao,
                                            width="content",
                                            hide_index=True,
                                            height=altura_tabela(df_abaixo_exibicao),
                                            column_config=centralizar(df_abaixo_exibicao, {
                                                "Média do Aluno": st.column_config.NumberColumn("Média do Aluno", format="%.1f"),
                                                "Menor Nota": st.column_config.NumberColumn("Menor Nota", format="%.1f"),
                                            }))
                                    else:
                                        st.success(f"Nenhum aluno com nota abaixo de {nota_corte:.1f} neste período.")
                                else:
                                    st.warning("Ainda não há notas lançadas para gerar o panorama desta turma neste período.")

                            elif tipo_consulta == "Comparativo entre Trimestres":
                                st.markdown(f"#### Comparativo entre Trimestres - Turma: {turma_selecionada}")
                                st.caption("Esta visão usa todos os trimestres cadastrados da turma, independente do período selecionado acima.")
                                
                                df_trim = buscar_medias_disciplina_por_trimestre(turma_selecionada)
                                
                                if df_trim.empty or df_trim['PERIODO'].nunique() < 2:
                                    st.warning("É preciso ter notas de pelo menos dois trimestres desta turma para fazer o comparativo. Importe as planilhas dos outros trimestres.")
                                else:
                                    nota_corte_comp = st.number_input(
                                        "Nota de corte geral (vale para todas as disciplinas):",
                                        min_value=0.0, max_value=10.0,
                                        value=float(st.session_state.params_avaliacao.get("media_minima", 6.0)),
                                        step=0.5, format="%.1f", key="corte_comp",
                                        help="É um único valor, igual para todas as disciplinas."
                                    )
                                    st.caption(f"Aqui a nota de corte é comparada com a média geral de cada aluno no trimestre (média de todas as disciplinas).")
                                    
                                    # Resumo da turma em cada trimestre
                                    df_resumo_trim = buscar_resumo_turma_por_trimestre(turma_selecionada, nota_corte_comp)
                                    st.markdown("##### Evolução Geral da Turma")
                                    colunas_trim = st.columns(len(df_resumo_trim))
                                    media_anterior = None
                                    for idx, linha in df_resumo_trim.iterrows():
                                        variacao = None if media_anterior is None else f"{linha['MEDIA_GERAL'] - media_anterior:+.1f}"
                                        colunas_trim[idx].metric(
                                            f"Média - {linha['PERIODO']}",
                                            f"{linha['MEDIA_GERAL']:.1f}",
                                            variacao
                                        )
                                        colunas_trim[idx].caption(f"Alunos com média geral abaixo de {nota_corte_comp:.1f}: **{int(linha['ALUNOS_ABAIXO'])} de {int(linha['TOTAL_ALUNOS'])}**")
                                        media_anterior = linha['MEDIA_GERAL']
                                    
                                    # Tabela disciplina x trimestre
                                    st.markdown("##### Média da Turma por Disciplina em Cada Trimestre")
                                    df_pivot = df_trim.pivot(index='DISCIPLINA', columns='PERIODO', values='MEDIA')
                                    periodos = list(df_pivot.columns)
                                    df_pivot['Variação (1º ao último)'] = (df_pivot[periodos[-1]] - df_pivot[periodos[0]]).round(1)
                                    df_pivot_exibicao = df_pivot.reset_index().rename(columns={'DISCIPLINA': 'Disciplina'})
                                    
                                    config_colunas = {p: st.column_config.NumberColumn(p, format="%.1f") for p in periodos}
                                    config_colunas['Variação (1º ao último)'] = st.column_config.NumberColumn('Variação (1º ao último)', format="%+.1f")
                                    tabela_centralizada(df_pivot_exibicao, width="content", hide_index=True, height=altura_tabela(df_pivot_exibicao), column_config=centralizar(df_pivot_exibicao, config_colunas))

                                    
                                    # Comparativo de um aluno
                                    st.markdown("---")
                                    st.markdown("##### Evolução de um Aluno")
                                    df_alunos_comp = buscar_alunos_da_turma_por_nome(turma_selecionada)
                                    lista_alunos_comp = ["Selecione..."] + list(df_alunos_comp['nome_aluno'])
                                    aluno_comp = st.selectbox("Aluno:", lista_alunos_comp, key="aluno_comp")
                                    
                                    if aluno_comp != "Selecione...":
                                        df_aluno_trim = buscar_notas_aluno_por_trimestre(turma_selecionada, aluno_comp)
                                        if not df_aluno_trim.empty:
                                            df_aluno_pivot = df_aluno_trim.pivot(index='DISCIPLINA', columns='PERIODO', values='NOTA_FINAL')
                                            periodos_aluno = list(df_aluno_pivot.columns)
                                            
                                            medias_aluno = df_aluno_pivot.mean().round(1)
                                            colunas_aluno = st.columns(len(periodos_aluno))
                                            for idx, per in enumerate(periodos_aluno):
                                                variacao = None if idx == 0 else f"{medias_aluno[per] - medias_aluno[periodos_aluno[idx - 1]]:+.1f}"
                                                colunas_aluno[idx].metric(f"Média do Aluno - {per}", f"{medias_aluno[per]:.1f}", variacao)
                                            
                                            if len(periodos_aluno) > 1:
                                                df_aluno_pivot['Variação (1º ao último)'] = (df_aluno_pivot[periodos_aluno[-1]] - df_aluno_pivot[periodos_aluno[0]]).round(1)
                                            df_aluno_exibicao = df_aluno_pivot.reset_index().rename(columns={'DISCIPLINA': 'Disciplina'})
                                            
                                            config_aluno = {p: st.column_config.NumberColumn(p, format="%.1f") for p in periodos_aluno}
                                            config_aluno['Variação (1º ao último)'] = st.column_config.NumberColumn('Variação (1º ao último)', format="%+.1f")
                                            tabela_centralizada(df_aluno_exibicao, width="content", hide_index=True, height=altura_tabela(df_aluno_exibicao), column_config=centralizar(df_aluno_exibicao, config_aluno))

                                        else:
                                            st.warning("Nenhuma nota encontrada para este aluno.")

                            elif tipo_consulta == "Boletim Individual do Aluno":
                                df_alunos = buscar_alunos_por_turma(periodo_selecionado, turma_selecionada)
                                if not df_alunos.empty:
                                    lista_alunos = ["Selecione..."] + list(df_alunos['nome_aluno'])
                                    aluno_selecionado = st.selectbox("Aluno:", lista_alunos)

                                    st.markdown("")
                                    
                                    if aluno_selecionado != "Selecione...":
                                        df_full = buscar_notas_aluno_com_ids(periodo_selecionado, turma_selecionada, aluno_selecionado)
                                        
                                        if not df_full.empty:
                                            st.markdown(f"##### Boletim do Aluno - {periodo_selecionado}")
                                            
                                            df_formatado = df_full.copy()
                                            for col in ['NOTA_PARCIAL', 'NOTA_DIVERSIFICADA', 'AVALIACAO_TRIMESTRAL', 'NOTA_FINAL']:
                                                df_formatado[col] = df_formatado[col].apply(lambda x: f"{float(x):.1f}" if pd.notnull(x) else "0.0")

                                            df_exibicao = df_formatado[['DISCIPLINA', 'NOTA_PARCIAL', 'NOTA_DIVERSIFICADA', 'AVALIACAO_TRIMESTRAL', 'NOTA_FINAL']].rename(columns={
                                                'DISCIPLINA': 'Disciplina',
                                                'NOTA_PARCIAL': 'Nota Parcial',
                                                'NOTA_DIVERSIFICADA': 'Nota Diversificada',
                                                'AVALIACAO_TRIMESTRAL': 'Avaliação Trimestral',
                                                'NOTA_FINAL': 'Nota Final'
                                            })
                                            tabela_centralizada(df_exibicao, width="content", hide_index=True, height=altura_tabela(df_exibicao), column_config=centralizar(df_exibicao))
                                            
                                            # ------------------------------------------------------------
                                            # Notas dos trimestres e média final ponderada
                                            # ------------------------------------------------------------
                                            cfg = st.session_state.params_avaliacao
                                            soma_pesos = cfg["peso_1"] + cfg["peso_2"] + cfg["peso_3"]
                                            pontos_minimos = cfg["media_minima"] * soma_pesos
                                            
                                            df_hist = buscar_notas_aluno_por_trimestre(turma_selecionada, aluno_selecionado)
                                            df_hist = df_hist[df_hist['PERIODO'] <= periodo_selecionado]
                                            df_hist_pivot = df_hist.pivot(index='DISCIPLINA', columns='PERIODO', values='NOTA_FINAL')
                                            periodos_hist = list(df_hist_pivot.columns)
                                            
                                            linhas_final = []
                                            for disciplina, notas in df_hist_pivot.iterrows():
                                                pontos, media_final, faltam, situacao, ano_completo = calcular_media_final(notas.to_dict())
                                                linha = {'Disciplina': disciplina}
                                                for per in periodos_hist:
                                                    linha[f"{per} (peso {peso_do_periodo(per)})"] = notas[per]
                                                linha['Pontos'] = pontos
                                                linha['Pontos que Faltam'] = faltam
                                                linha['Média Final' if ano_completo else 'Média até o Momento'] = media_final
                                                linha['Situação'] = situacao
                                                linhas_final.append(linha)
                                            df_final = pd.DataFrame(linhas_final)
                                            
                                            st.markdown("##### Notas dos Trimestres e Média Final")
                                            st.caption(
                                                f"Média Final = (1º Tri × {cfg['peso_1']} + 2º Tri × {cfg['peso_2']} + 3º Tri × {cfg['peso_3']}) ÷ {soma_pesos}. "
                                                f"Média mínima da escola: {cfg['media_minima']:.1f} (mínimo de {pontos_minimos:.1f} pontos). "
                                                "Os pesos podem ser alterados em Cadastro > 1. Definir Critérios."
                                            )
                                            
                                            if not df_final.empty:
                                                coluna_media = 'Média Final' if 'Média Final' in df_final.columns else 'Média até o Momento'
                                                media_final_aluno = round(df_final[coluna_media].mean(), 1)
                                                qtd_atingiu = int((df_final['Pontos'] >= pontos_minimos).sum())
                                                c_f1, c_f2, c_f3 = st.columns(3)
                                                c_f1.metric("Média Final Geral do Aluno" if coluna_media == 'Média Final' else "Média Geral até o Momento", f"{media_final_aluno:.1f}")
                                                c_f2.metric("Disciplinas com a Média Atingida", f"{qtd_atingiu} de {len(df_final)}")
                                                c_f3.metric("Trimestres Considerados", ", ".join(p.split()[0] for p in periodos_hist))
                                                
                                                config_final = {c: st.column_config.NumberColumn(c, format="%.1f") for c in df_final.columns if c not in ('Disciplina', 'Situação')}
                                                tabela_centralizada(df_final, width="content", hide_index=True, height=altura_tabela(df_final), column_config=centralizar(df_final, config_final))
                                            
                                            # Detalhes dos trimestres anteriores (expansível)
                                            periodos_anteriores = [p for p in periodos_hist if p < periodo_selecionado]
                                            if periodos_anteriores:
                                                with st.expander("Ver notas detalhadas dos trimestres anteriores"):
                                                    for per_ant in periodos_anteriores:
                                                        df_ant = buscar_notas_aluno_com_ids(per_ant, turma_selecionada, aluno_selecionado)
                                                        if not df_ant.empty:
                                                            st.markdown(f"**{per_ant}**")
                                                            df_ant_exibicao = df_ant[['DISCIPLINA', 'NOTA_PARCIAL', 'NOTA_DIVERSIFICADA', 'AVALIACAO_TRIMESTRAL', 'NOTA_FINAL']].rename(columns={
                                                                'DISCIPLINA': 'Disciplina',
                                                                'NOTA_PARCIAL': 'Nota Parcial',
                                                                'NOTA_DIVERSIFICADA': 'Nota Diversificada',
                                                                'AVALIACAO_TRIMESTRAL': 'Avaliação Trimestral',
                                                                'NOTA_FINAL': 'Nota Final'
                                                            })
                                                            config_ant = {c: st.column_config.NumberColumn(c, format="%.1f") for c in df_ant_exibicao.columns if c != 'Disciplina'}
                                                            tabela_centralizada(df_ant_exibicao, width="content", hide_index=True, height=altura_tabela(df_ant_exibicao), column_config=centralizar(df_ant_exibicao, config_ant))
                                            
                                            st.markdown("---")
                                            alterar_notas = st.checkbox("Habilitar modo de edição e exclusão de notas")
                                            
                                            if alterar_notas:
                                                st.markdown("##### Editar ou Excluir Notas por Disciplina")
                                                for index, row in df_full.iterrows():
                                                    with st.container():
                                                        col_form, col_del = st.columns([0.85, 0.15])
                                                        
                                                        with col_form:
                                                            with st.form(f"form_alt_{row['nota_id']}"):
                                                                st.write(f"**Disciplina:** {row['DISCIPLINA']}")
                                                                c_n1, c_n2, c_n3 = st.columns(3)
                                                                with c_n1:
                                                                    novo_parcial = st.number_input("Parcial", value=round(float(row['NOTA_PARCIAL'] or 0.0), 1), step=0.1, format="%.1f", key=f"p_{row['nota_id']}")
                                                                with c_n2:
                                                                    novo_div = st.number_input("Diversificada", value=round(float(row['NOTA_DIVERSIFICADA'] or 0.0), 1), step=0.1, format="%.1f", key=f"d_{row['nota_id']}")
                                                                with c_n3:
                                                                    novo_trim = st.number_input("Avaliação", value=round(float(row['AVALIACAO_TRIMESTRAL'] or 0.0), 1), step=0.1, format="%.1f", key=f"t_{row['nota_id']}")
                                                                
                                                                nf_calc, lista_erros = validar_e_calcular_notas(novo_parcial, novo_div, novo_trim)
                                                                st.caption(f"Nota Final Estimada: **{nf_calc:.1f}**")
                                                                
                                                                salvar_alt = st.form_submit_button("Atualizar Nota")
                                                                if salvar_alt:
                                                                    if lista_erros:
                                                                        for err in lista_erros:
                                                                            st.error(err)
                                                                    else:
                                                                        atualizar_nota_por_id(row['nota_id'], novo_parcial, novo_div, novo_trim)
                                                                        st.success(f"Nota de {row['DISCIPLINA']} atualizada com sucesso.")
                                                                        st.rerun()
                                                        
                                                        with col_del:
                                                            st.write("") 
                                                            st.write("")
                                                            if st.button("Excluir", key=f"del_{row['nota_id']}", help=f"Excluir registro de {row['DISCIPLINA']}"):
                                                                deletar_nota_por_id(row['nota_id'])
                                                                st.warning(f"Registro de {row['DISCIPLINA']} excluído!")
                                                                st.rerun()
                                        else:
                                            st.warning("Nenhum dado encontrado para este aluno.")
                                    else:
                                        st.info("Selecione um aluno para visualizar o boletim.")
                                else:
                                    st.info("Nenhum aluno encontrado para esta turma.")
                        else:
                            st.info("Selecione uma turma.")
                    else:
                        st.info("Nenhuma turma encontrada para este período.")
                else:
                    st.info("Selecione um período letivo para iniciar a consulta.")
            else:
                st.info("O banco de dados está vazio. Utilize o módulo de cadastro para inserir dados.")
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
    else:
        st.info("Nenhum registro encontrado. Cadastre dados para começar.")

# =========================================================================
# MÓDULO 3: ANÁLISES E GRÁFICOS (AC4)
# =========================================================================
elif menu_principal == "Análises e Gráficos":
    st.subheader("Análises Comparativas com Filtros e Gráficos")
    
    df_base = buscar_base_analise() if os.path.exists(DB_PATH) else pd.DataFrame()
    
    if df_base.empty:
        st.info("Ainda não há notas cadastradas. Importe as planilhas no módulo Cadastro para gerar as análises.")
    else:
        df_base['SERIE'] = df_base['TURMA'].apply(extrair_serie)
        
        # ------------------------------------------------------------
        # Filtros
        # ------------------------------------------------------------
        with st.expander("Filtros", expanded=True):
            st.caption("Escolha os filtros desejados. Campo deixado em branco considera todas as opções.")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                periodos_disp = sorted(df_base['PERIODO'].unique())
                periodos_sel = st.multiselect("Trimestres:", periodos_disp, placeholder="Selecione os trimestres...")
                
                series_disp = sorted(df_base['SERIE'].unique())
                series_sel = st.multiselect("Séries:", series_disp, placeholder="Selecione as séries...")
            with col_f2:
                series_para_turmas = series_sel if series_sel else series_disp
                turmas_disp = sorted(df_base.loc[df_base['SERIE'].isin(series_para_turmas), 'TURMA'].unique())
                turmas_sel = st.multiselect("Turmas:", turmas_disp, placeholder="Selecione as turmas...")
                
                componentes_disp = sorted(df_base['COMPONENTE'].unique())
                componentes_sel = st.multiselect("Componentes Curriculares:", componentes_disp, placeholder="Selecione os componentes...")
            
            media_escola = float(st.session_state.params_avaliacao.get("media_minima", 6.0))
            nota_corte = st.number_input("Nota de corte (média mínima):", min_value=0.0, max_value=10.0, value=media_escola, step=0.5, format="%.1f", key="corte_analise")
        
        nenhum_filtro = not (periodos_sel or series_sel or turmas_sel or componentes_sel)
        
        # Campo vazio = todas as opções daquele filtro
        df_filtro = df_base[
            df_base['PERIODO'].isin(periodos_sel if periodos_sel else periodos_disp)
            & df_base['SERIE'].isin(series_para_turmas)
            & df_base['TURMA'].isin(turmas_sel if turmas_sel else turmas_disp)
            & df_base['COMPONENTE'].isin(componentes_sel if componentes_sel else componentes_disp)
        ]
        
        if nenhum_filtro:
            st.info("Selecione pelo menos um filtro acima (trimestre, série, turma ou componente) para gerar as análises e os gráficos.")
        elif df_filtro.empty:
            st.warning("Nenhum dado encontrado para os filtros selecionados. Ajuste os filtros acima.")
        else:
            # Indicadores gerais do filtro
            c_i1, c_i2, c_i3, c_i4 = st.columns(4)
            c_i1.metric("Média Geral", f"{df_filtro['NOTA_FINAL'].mean():.1f}")
            c_i2.metric("Turmas", df_filtro['TURMA'].nunique())
            c_i3.metric("Alunos", df_filtro['ALUNO_ID'].nunique())
            perc_geral = (df_filtro['NOTA_FINAL'] < nota_corte).mean() * 100
            c_i4.metric(f"Notas Abaixo de {nota_corte:.1f}", f"{perc_geral:.0f}%")
            
            aba1, aba2, aba3, aba4, aba5 = st.tabs([
                "Turmas por Componente",
                "Comparação entre Séries",
                "Comparação entre Componentes",
                "Evolução nos Trimestres",
                "Dados Filtrados"
            ])
            
            # ------------------------------------------------------------
            # Aba 1: como cada turma se saiu em um componente
            # ------------------------------------------------------------
            with aba1:
                st.markdown("##### Desempenho das Turmas em um Componente Curricular")
                componentes_filtro = sorted(df_filtro['COMPONENTE'].unique())
                comp_escolhido = st.selectbox("Componente:", componentes_filtro, index=None, placeholder="Selecione o componente...", key="comp_aba1")
                
                if comp_escolhido is None:
                    st.info("Selecione um componente curricular para comparar as turmas.")
                else:
                    df_comp = df_filtro[df_filtro['COMPONENTE'] == comp_escolhido]
                    resumo_comp = resumir_notas(df_comp, ['TURMA', 'PERIODO'], nota_corte)
                
                    pivot_comp = resumo_comp.pivot(index='TURMA', columns='PERIODO', values='MEDIA').rename_axis(index='Turma', columns='Trimestre')
                    st.bar_chart(pivot_comp, stack=False, color=cores_para(len(pivot_comp.columns)), x_label="Turma", y_label="Média", height=420)
                
                    resumo_turma = resumir_notas(df_comp, ['TURMA'], nota_corte).sort_values('MEDIA', ascending=False)
                    tabela_aba1 = resumo_turma[['TURMA', 'MEDIA', 'ALUNOS', 'PERC_ABAIXO']].rename(columns={
                        'TURMA': 'Turma',
                        'MEDIA': f'Média em {comp_escolhido}',
                        'ALUNOS': 'Alunos',
                        'PERC_ABAIXO': f'% Notas Abaixo de {nota_corte:.1f}'
                    })
                    st.dataframe(tabela_aba1, width="content", hide_index=True, height=altura_tabela(tabela_aba1), column_config=centralizar(tabela_aba1))
                    if len(resumo_turma) > 1:
                        melhor = resumo_turma.iloc[0]
                        pior = resumo_turma.iloc[-1]
                        st.caption(f"Maior média: **{melhor['TURMA']}** ({melhor['MEDIA']:.1f}) | Menor média: **{pior['TURMA']}** ({pior['MEDIA']:.1f}) | Diferença: **{melhor['MEDIA'] - pior['MEDIA']:.1f}** ponto(s).")
            
            # ------------------------------------------------------------
            # Aba 2: comparação entre séries
            # ------------------------------------------------------------
            with aba2:
                st.markdown("##### Média por Série em Cada Trimestre")
                st.caption("Considera os componentes e turmas selecionados nos filtros. Turmas da mesma série são agrupadas.")
                resumo_serie = resumir_notas(df_filtro, ['SERIE', 'PERIODO'], nota_corte)
                pivot_serie = resumo_serie.pivot(index='SERIE', columns='PERIODO', values='MEDIA').rename_axis(index='Série', columns='Trimestre')
                st.bar_chart(pivot_serie, stack=False, color=cores_para(len(pivot_serie.columns)), x_label="Série", y_label="Média", height=420)
                
                tabela_serie = pivot_serie.reset_index()
                resumo_serie_total = resumir_notas(df_filtro, ['SERIE'], nota_corte)
                tabela_serie['Média no Período Filtrado'] = resumo_serie_total.set_index('SERIE').loc[tabela_serie['Série'], 'MEDIA'].values
                tabela_serie['Turmas'] = df_filtro.groupby('SERIE')['TURMA'].nunique().loc[tabela_serie['Série']].values
                tabela_serie[f'% Notas Abaixo de {nota_corte:.1f}'] = resumo_serie_total.set_index('SERIE').loc[tabela_serie['Série'], 'PERC_ABAIXO'].values
                config_serie = {c: st.column_config.NumberColumn(c, format="%.1f") for c in list(pivot_serie.columns) + ['Média no Período Filtrado']}
                st.dataframe(tabela_serie, width="content", hide_index=True, height=altura_tabela(tabela_serie), column_config=centralizar(tabela_serie, config_serie))
            
            # ------------------------------------------------------------
            # Aba 3: comparação entre componentes
            # ------------------------------------------------------------
            with aba3:
                st.markdown("##### Média por Componente Curricular nas Turmas Selecionadas")
                st.caption("Use os filtros para escolher as turmas e os trimestres. Cada cor representa uma turma.")
                resumo_comp_turma = resumir_notas(df_filtro, ['COMPONENTE', 'TURMA'], nota_corte)
                pivot_comp_turma = resumo_comp_turma.pivot(index='COMPONENTE', columns='TURMA', values='MEDIA').rename_axis(index='Componente', columns='Turma')
                st.bar_chart(
                    pivot_comp_turma,
                    stack=False,
                    horizontal=True,
                    color=cores_para(len(pivot_comp_turma.columns)),
                    x_label="Componente",
                    y_label="Média",
                    height=max(400, 18 * len(pivot_comp_turma) * len(pivot_comp_turma.columns) + 80)
                )
                
                tabela_comp = pivot_comp_turma.reset_index()
                tabela_comp['Média Geral'] = pivot_comp_turma.mean(axis=1).round(1).values
                tabela_comp = tabela_comp.sort_values('Média Geral', ascending=False)
                config_comp = {c: st.column_config.NumberColumn(c, format="%.1f") for c in tabela_comp.columns if c != 'Componente'}
                st.dataframe(tabela_comp, width="content", hide_index=True, height=altura_tabela(tabela_comp), column_config=centralizar(tabela_comp, config_comp))
            
            # ------------------------------------------------------------
            # Aba 4: evolução ao longo dos trimestres
            # ------------------------------------------------------------
            with aba4:
                st.markdown("##### Evolução da Média ao Longo dos Trimestres")
                opcoes_evol = ["Todos os componentes filtrados"] + sorted(df_filtro['COMPONENTE'].unique())
                comp_evol = st.selectbox("Componente:", opcoes_evol, key="comp_evol")
                df_evol = df_filtro if comp_evol == "Todos os componentes filtrados" else df_filtro[df_filtro['COMPONENTE'] == comp_evol]
                
                resumo_evol = resumir_notas(df_evol, ['PERIODO', 'TURMA'], nota_corte)
                pivot_evol = resumo_evol.pivot(index='PERIODO', columns='TURMA', values='MEDIA').rename_axis(index='Trimestre', columns='Turma')
                
                if len(pivot_evol) < 2:
                    st.info("Selecione pelo menos dois trimestres nos filtros para ver a evolução.")
                st.line_chart(pivot_evol, color=cores_para(len(pivot_evol.columns)), x_label="Trimestre", y_label="Média", height=420)
                
                tabela_evol = pivot_evol.T.reset_index()
                periodos_evol = list(pivot_evol.index)
                if len(periodos_evol) > 1:
                    tabela_evol['Variação (1º ao último)'] = (tabela_evol[periodos_evol[-1]] - tabela_evol[periodos_evol[0]]).round(1)
                config_evol = {c: st.column_config.NumberColumn(c, format="%.1f") for c in periodos_evol}
                config_evol['Variação (1º ao último)'] = st.column_config.NumberColumn('Variação (1º ao último)', format="%+.1f")
                st.dataframe(tabela_evol, width="content", hide_index=True, height=altura_tabela(tabela_evol), column_config=centralizar(tabela_evol, config_evol))
                st.caption("Turmas que não têm notas em algum trimestre aparecem com o valor em branco.")
            
            # ------------------------------------------------------------
            # Aba 5: dados filtrados e exportação
            # ------------------------------------------------------------
            with aba5:
                st.markdown("##### Resumo dos Dados Filtrados")
                resumo_geral = resumir_notas(df_filtro, ['PERIODO', 'SERIE', 'TURMA', 'COMPONENTE'], nota_corte)
                tabela_geral = resumo_geral[['PERIODO', 'SERIE', 'TURMA', 'COMPONENTE', 'MEDIA', 'ALUNOS', 'ABAIXO', 'PERC_ABAIXO']].rename(columns={
                    'PERIODO': 'Trimestre',
                    'SERIE': 'Série',
                    'TURMA': 'Turma',
                    'COMPONENTE': 'Componente',
                    'MEDIA': 'Média',
                    'ALUNOS': 'Alunos',
                    'ABAIXO': f'Alunos Abaixo de {nota_corte:.1f}',
                    'PERC_ABAIXO': '% Abaixo'
                })
                st.dataframe(tabela_geral, width="content", hide_index=True, height=min(altura_tabela(tabela_geral), 700),
                             column_config=centralizar(tabela_geral, {'Média': st.column_config.NumberColumn('Média', format="%.1f")}))
                st.caption(f"{len(tabela_geral)} linha(s).")
                
                csv_dados = tabela_geral.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    "Baixar dados filtrados (CSV para Excel)",
                    data=csv_dados,
                    file_name="analise_desempenho_filtrada.csv",
                    mime="text/csv"
                )

# =========================================================================
# MÓDULO 2: CADASTRO E LANÇAMENTOS
# =========================================================================
elif menu_principal == "Cadastro":
    sub_cadastro = st.radio(
        "Tipo de Cadastro / Lançamento:", 
        [
            "1. Definir Critérios e Limites (Obrigatório)", 
            "2. Importar Planilha (Lote)", 
            "3. Lançamento em Lote (Componente)", 
            "4. Cadastro Individual",
            "5. Corrigir ou Unir Turmas"
        ], 
        horizontal=False
    )
    st.markdown("---")
    
    if sub_cadastro == "1. Definir Critérios e Limites (Obrigatório)":
        st.subheader("Configuração Obrigatória de Notas Máximas por Critério")
        st.info("Defina o teto máximo de pontuação para cada instrumento de avaliação antes de prosseguir com os lançamentos.")
        
        cfg = st.session_state.params_avaliacao
        
        with st.form("form_parametros"):
            col_c1, col_c2, col_c3 = st.columns(3)
            
            with col_c1:
                max_parcial_input = st.number_input("Nota Máxima - Parcial", min_value=0.0, max_value=10.0, value=cfg["max_parcial"], step=0.5, format="%.1f")
            with col_c2:
                max_diversificada_input = st.number_input("Nota Máxima - Diversificada", min_value=0.0, max_value=10.0, value=cfg["max_diversificada"], step=0.5, format="%.1f")
            with col_c3:
                max_trimestral_input = st.number_input("Nota Máxima - Trimestral", min_value=0.0, max_value=10.0, value=cfg["max_trimestral"], step=0.5, format="%.1f")
            
            st.markdown("##### Pesos dos Trimestres para a Média Final")
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            with col_p1:
                peso_1_input = st.number_input("Peso - 1º Trimestre", min_value=1, max_value=10, value=int(cfg["peso_1"]), step=1)
            with col_p2:
                peso_2_input = st.number_input("Peso - 2º Trimestre", min_value=1, max_value=10, value=int(cfg["peso_2"]), step=1)
            with col_p3:
                peso_3_input = st.number_input("Peso - 3º Trimestre", min_value=1, max_value=10, value=int(cfg["peso_3"]), step=1)
            with col_p4:
                media_minima_input = st.number_input("Média Mínima da Escola", min_value=0.0, max_value=10.0, value=float(cfg["media_minima"]), step=0.5, format="%.1f")
            
            soma_pesos_cfg = peso_1_input + peso_2_input + peso_3_input
            st.caption(
                f"Média Final = (1º Tri × {peso_1_input} + 2º Tri × {peso_2_input} + 3º Tri × {peso_3_input}) ÷ {soma_pesos_cfg}. "
                f"Para atingir a média {media_minima_input:.1f}, o aluno precisa de no mínimo {media_minima_input * soma_pesos_cfg:.1f} pontos."
            )
                
            salvar_params = st.form_submit_button("Salvar Critérios e Ativar Lançamentos")
            
            if salvar_params:
                st.session_state.params_avaliacao = {
                    "max_parcial": max_parcial_input,
                    "max_diversificada": max_diversificada_input,
                    "max_trimestral": max_trimestral_input,
                    "peso_1": peso_1_input,
                    "peso_2": peso_2_input,
                    "peso_3": peso_3_input,
                    "media_minima": media_minima_input,
                    "configurado": True
                }
                st.success("Critérios salvos com sucesso! A nota de cada trimestre será a somatória simples dos instrumentos e a média final usará os pesos definidos. Agora você já pode usar os lançamentos.")

        if st.session_state.params_avaliacao["configurado"]:
            st.success("Status: Critérios configurados e ativos no sistema.")
        else:
            st.warning("Você precisa salvar os critérios pelo menos uma vez antes de validar os lançamentos.")

    elif sub_cadastro == "2. Importar Planilha (Lote)":
        st.subheader("Importação em Lote via Planilha Excel")
        
        periodo_imp = st.selectbox("Período Letivo:", ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE"])
        arquivo_enviado = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])
        
        if arquivo_enviado is not None:
            if st.button("Pré-analisar Planilha"):
                try:
                    # Remove o trimestre do nome do arquivo (ex: "1 série A-1tri" vira "1 SÉRIE A"),
                    # para que os três trimestres fiquem na mesma turma e possam ser comparados
                    nome_base = os.path.splitext(arquivo_enviado.name)[0]
                    nome_base = re.sub(r'[\s_-]*\d\s*º?\s*tri(mestre)?\s*$', '', nome_base, flags=re.IGNORECASE)
                    nome_turma = nome_base.replace("_", " ").strip().upper()
                    
                    bytes_data = arquivo_enviado.getvalue()
                    xls = pd.ExcelFile(io.BytesIO(bytes_data))
                    
                    if not xls.sheet_names:
                        st.error("O arquivo Excel enviado não possui nenhuma aba (disciplina).")
                        st.stop()
                    
                    registros_validos = []
                    registros_com_erro = []
                    
                    for disciplina in xls.sheet_names:
                        df = pd.read_excel(io.BytesIO(bytes_data), sheet_name=disciplina, header=None)
                        
                        start_row = -1
                        for i in range(len(df)):
                            val0 = df.iloc[i, 0]
                            try:
                                if int(val0) == 1:
                                    start_row = i
                                    break
                            except:
                                continue
                                
                        if start_row == -1:
                            start_row = 5
                        
                        num_cols = df.shape[1]
                        
                        for i in range(start_row, len(df)):
                            num_chamada = df.iloc[i, 0]
                            nome_aluno = df.iloc[i, 1]
                            
                            if pd.isna(num_chamada) or pd.isna(nome_aluno):
                                continue
                                
                            nome_str = str(nome_aluno).strip().upper()
                            if "TOTAL" in nome_str or "MÉDIA" in nome_str or len(nome_str) < 2:
                                continue
                            
                            tem_problema = False
                            motivo_problema = []

                            if verificar_nota_existente(periodo_imp, nome_turma, nome_str, disciplina.upper()):
                                tem_problema = True
                                motivo_problema.append("Registro duplicado (já existe nota para este aluno nesta disciplina no período)")

                            nota_parcial = 0.0
                            nota_diversificada = 0.0
                            avaliacao_trimestral = 0.0
                            nota_final = None
                            
                            for col_idx in range(2, num_cols):
                                val = df.iloc[i, col_idx]
                                if pd.isna(val):
                                    continue
                                    
                                nome_coluna = ""
                                try:
                                    h2 = str(df.iloc[2, col_idx]).strip().upper()
                                    h3 = str(df.iloc[3, col_idx]).strip().upper()
                                    if h2 and h2 != 'NAN':
                                        nome_coluna = h2
                                    elif h3 and h3 != 'NAN':
                                        nome_coluna = h3
                                except:
                                    pass
                                
                                if "PARCIAL" in nome_coluna:
                                    nota_parcial, err, msg = processar_valor_celula(val, "Parcial")
                                    if err:
                                        tem_problema = True
                                        motivo_problema.append(msg)
                                elif "DIVERSIFICADA" in nome_coluna:
                                    nota_diversificada, err, msg = processar_valor_celula(val, "Diversificada")
                                    if err:
                                        tem_problema = True
                                        motivo_problema.append(msg)
                                elif "TRIMESTRAL" in nome_coluna:
                                    avaliacao_trimestral, err, msg = processar_valor_celula(val, "Trimestral")
                                    if err:
                                        tem_problema = True
                                        motivo_problema.append(msg)
                                elif "TOTAL" in nome_coluna or col_idx == num_cols - 1:
                                    nota_final, err, msg = processar_valor_celula(val, "Total")
                                    if err:
                                        tem_problema = True
                                        motivo_problema.append(msg)

                            nf_calculada, errs_validacao = validar_e_calcular_notas(nota_parcial, nota_diversificada, avaliacao_trimestral)
                            if errs_validacao:
                                tem_problema = True
                                motivo_problema.extend(errs_validacao)

                            if nota_final is None:
                                nota_final = nf_calculada

                            try:
                                num_chamada_str = str(int(float(num_chamada)))
                            except:
                                num_chamada_str = str(num_chamada).strip()

                            registro = {
                                "Disciplina": disciplina.upper(),
                                "Chamada": num_chamada_str,
                                "Aluno": nome_str,
                                "Parcial": round(float(nota_parcial), 1),
                                "Diversificada": round(float(nota_diversificada), 1),
                                "Trimestral": round(float(avaliacao_trimestral), 1),
                                "Nota Final": round(float(nota_final), 1)
                            }

                            if tem_problema:
                                registro["Motivo da Inconsistência"] = "; ".join(motivo_problema)
                                registros_com_erro.append(registro)
                            else:
                                registros_validos.append(registro)

                    st.session_state.importacao_pendente = {
                        "nome_turma": nome_turma,
                        "periodo": periodo_imp,
                        "registros_validos": registros_validos,
                        "df_com_erro": pd.DataFrame(registros_com_erro) if registros_com_erro else pd.DataFrame()
                    }
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao analisar planilha: {e}")

        if st.session_state.importacao_pendente is not None:
            pendente = st.session_state.importacao_pendente
            qtd_validos = len(pendente["registros_validos"])
            df_erros = pendente["df_com_erro"]
            qtd_erros = len(df_erros)

            st.info(f"Resumo da Pré-análise (Turma: {pendente['nome_turma']} - {pendente['periodo']})")
            
            # Permite corrigir o nome da turma antes de gravar
            turma_confirmada = st.text_input(
                "Nome da turma (corrija se necessário antes de gravar):",
                value=pendente["nome_turma"],
                key="turma_importacao"
            ).strip().upper()
            df_turmas_existentes = buscar_turmas()
            if not df_turmas_existentes.empty:
                st.caption("Turmas já cadastradas: " + ", ".join(df_turmas_existentes['nome_turma']) + ". Use exatamente o mesmo nome para juntar os trimestres na mesma turma.")
            st.write(f"- Registros sem problemas prontos para importar: **{qtd_validos}**")
            st.write(f"- Registros que precisam de revisão/confirmação (incluindo duplicados): **{qtd_erros}**")

            if qtd_erros > 0:
                st.warning("Foram identificados itens com duplicidade ou inconsistência. Confirme ou ajuste os valores abaixo antes de salvar (se confirmar, os duplicados serão atualizados):")
                
                df_erros_editado = st.data_editor(
                    df_erros,
                    column_config={
                        "Disciplina": st.column_config.TextColumn("Disciplina", disabled=True),
                        "Chamada": st.column_config.TextColumn("Chamada", disabled=True),
                        "Aluno": st.column_config.TextColumn("Aluno", disabled=True),
                        "Parcial": st.column_config.NumberColumn("Parcial", format="%.1f", step=0.1, min_value=0.0),
                        "Diversificada": st.column_config.NumberColumn("Diversificada", format="%.1f", step=0.1, min_value=0.0),
                        "Trimestral": st.column_config.NumberColumn("Trimestral", format="%.1f", step=0.1, min_value=0.0),
                        "Nota Final": st.column_config.NumberColumn("Nota Final", format="%.1f", disabled=True),
                        "Motivo da Inconsistência": st.column_config.TextColumn("Motivo da Inconsistência", disabled=True),
                    },
                    hide_index=True,
                    width="stretch",
                    key="tabela_itens_com_erro"
                )
            else:
                df_erros_editado = pd.DataFrame()
                st.success("Nenhum erro ou duplicidade encontrado! Todos os registros estão perfeitos.")

            c_confirm, c_cancel = st.columns(2)
            
            with c_confirm:
                if st.button("Confirmar e Gravar Todos no Banco de Dados", type="primary"):
                    try:
                        todos_para_salvar = list(pendente["registros_validos"])
                        erros_Finais = []

                        if not df_erros_editado.empty:
                            for _, row in df_erros_editado.iterrows():
                                p = round(float(row["Parcial"]), 1)
                                d = round(float(row["Diversificada"]), 1)
                                t = round(float(row["Trimestral"]), 1)
                                
                                nf_calc, errs = validar_e_calcular_notas(p, d, t)
                                if errs:
                                    erros_Finais.append(f"Aluno **{row['Aluno']}** ({row['Disciplina']}): " + " | ".join(errs))
                                else:
                                    todos_para_salvar.append({
                                        "Disciplina": row["Disciplina"],
                                        "Chamada": row["Chamada"],
                                        "Aluno": row["Aluno"],
                                        "Parcial": p,
                                        "Diversificada": d,
                                        "Trimestral": t,
                                        "Nota Final": nf_calc
                                    })

                        if erros_Finais:
                            st.error("Corrija os erros abaixo antes de salvar:")
                            for err in erros_Finais:
                                st.warning(err)
                        else:
                            conexao = obter_conexao()
                            cursor = conexao.cursor()
                            cursor.execute("PRAGMA foreign_keys = ON;")
                            
                            nome_turma = turma_confirmada if turma_confirmada else pendente["nome_turma"]
                            periodo_imp = pendente["periodo"]
                            
                            cursor.execute("INSERT OR IGNORE INTO turmas (nome_turma) VALUES (?)", (nome_turma,))
                            cursor.execute("SELECT id FROM turmas WHERE nome_turma = ?", (nome_turma,))
                            turma_id = cursor.fetchone()[0]
                            
                            for reg in todos_para_salvar:
                                disc = reg["Disciplina"]
                                cursor.execute("INSERT OR IGNORE INTO disciplinas (nome_disciplina) VALUES (?)", (disc,))
                                cursor.execute("SELECT id FROM disciplinas WHERE nome_disciplina = ?", (disc,))
                                disciplina_id = cursor.fetchone()[0]
                                
                                aluno_str = reg["Aluno"]
                                num_chamada_str = reg["Chamada"]
                                
                                cursor.execute('SELECT id FROM alunos WHERE nome_aluno = ? AND turma_id = ?', (aluno_str, turma_id))
                                aluno_res = cursor.fetchone()
                                
                                if aluno_res:
                                    aluno_id = aluno_res[0]
                                    cursor.execute("UPDATE alunos SET numero_chamada = ? WHERE id = ?", (num_chamada_str, aluno_id))
                                else:
                                    cursor.execute('INSERT INTO alunos (nome_aluno, numero_chamada, turma_id) VALUES (?, ?, ?)', (aluno_str, num_chamada_str, turma_id))
                                    aluno_id = cursor.lastrowid
                                    
                                cursor.execute('DELETE FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_imp, aluno_id, disciplina_id))
                                cursor.execute('''
                                    INSERT INTO notas (periodo, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (periodo_imp, aluno_id, disciplina_id, reg["Parcial"], reg["Diversificada"], reg["Trimestral"], reg["Nota Final"]))

                            conexao.commit()
                            conexao.close()
                            
                            st.session_state.importacao_pendente = None
                            st.success("Planilha importada e gravada no banco de dados com sucesso!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco de dados: {e}")

            with c_cancel:
                if st.button("Cancelar Importação"):
                    st.session_state.importacao_pendente = None
                    st.info("Importação cancelada pelo usuário.")
                    st.rerun()

    elif sub_cadastro == "3. Lançamento em Lote (Componente)":
        st.subheader("Lançamento Manual em Lote por Disciplina")
        
        periodo_lote = st.selectbox("Período Letivo:", ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE"], key="lote_per")
        
        df_turmas_lote = buscar_turmas()
        df_disc_lote = buscar_disciplinas()
        
        turmas_existentes = list(df_turmas_lote['nome_turma']) if not df_turmas_lote.empty else []
        opcoes_turma_lote = ["Selecione..."] + turmas_existentes + ["+ Nova Turma"]
        
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            sel_turma_lote = st.selectbox("Turma:", opcoes_turma_lote)
            turma_final_lote = ""
            if sel_turma_lote == "+ Nova Turma":
                turma_final_lote = st.text_input("Digite o nome da Nova Turma:").strip().upper()
            elif sel_turma_lote != "Selecione...":
                turma_final_lote = sel_turma_lote
                
        with col_l2:
            disciplinas_existentes = list(df_disc_lote['nome_disciplina']) if not df_disc_lote.empty else []
            opcoes_disc_lote = ["Selecione..."] + disciplinas_existentes + ["+ Novo Componente"]
            sel_disc_lote = st.selectbox("Componente Curricular (Disciplina):", opcoes_disc_lote)
            disc_final_lote = ""
            if sel_disc_lote == "+ Novo Componente":
                disc_final_lote = st.text_input("Digite o nome da Nova Disciplina:").strip().upper()
            elif sel_disc_lote != "Selecione...":
                disc_final_lote = sel_disc_lote
                
        if sel_turma_lote != "Selecione..." and sel_disc_lote != "Selecione..." and turma_final_lote and disc_final_lote:
            conexao_temp = obter_conexao()
            cursor_temp = conexao_temp.cursor()
            cursor_temp.execute("INSERT OR IGNORE INTO turmas (nome_turma) VALUES (?)", (turma_final_lote,))
            cursor_temp.execute("SELECT id FROM turmas WHERE nome_turma = ?", (turma_final_lote,))
            turma_sel_id = cursor_temp.fetchone()[0]
            
            cursor_temp.execute("INSERT OR IGNORE INTO disciplinas (nome_disciplina) VALUES (?)", (disc_final_lote,))
            cursor_temp.execute("SELECT id FROM disciplinas WHERE nome_disciplina = ?", (disc_final_lote,))
            disc_sel_id = cursor_temp.fetchone()[0]
            conexao_temp.commit()
            conexao_temp.close()
            
            df_alunos_sala = buscar_alunos_da_turma_por_id(turma_sel_id)
            
            if df_alunos_sala.empty:
                st.info("Nenhum aluno cadastrado nesta turma. Cadastre alunos no modo 'Cadastro Individual'.")
            else:
                cfg = st.session_state.params_avaliacao
                st.markdown(f"##### Lançando notas para a turma **{turma_final_lote}** em **{disc_final_lote}**")
                st.info(f"Limites vigentes: Parcial (0 a {cfg['max_parcial']:.1f}), Diversificada (0 a {cfg['max_diversificada']:.1f}), Trimestral (0 a {cfg['max_trimestral']:.1f}) | Nota Final (0 a 10.0)")
                
                tabela_dados = []
                for _, al in df_alunos_sala.iterrows():
                    al_id = al['id']
                    
                    conexao_n = obter_conexao()
                    cursor_n = conexao_n.cursor()
                    cursor_n.execute('SELECT nota_parcial, nota_diversificada, avaliacao_trimestral FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_lote, al_id, disc_sel_id))
                    res_nota = cursor_n.fetchone()
                    conexao_n.close()
                    
                    val_p = round(float(res_nota[0]), 1) if res_nota and res_nota[0] is not None else 0.0
                    val_d = round(float(res_nota[1]), 1) if res_nota and res_nota[1] is not None else 0.0
                    val_t = round(float(res_nota[2]), 1) if res_nota and res_nota[2] is not None else 0.0
                    
                    tabela_dados.append({
                        "aluno_id": al_id,
                        "Chamada": str(al['numero_chamada'] or "-"),
                        "Aluno": al['nome_aluno'],
                        "Parcial": str(val_p),
                        "Diversificada": str(val_d),
                        "Trimestral": str(val_t)
                    })
                
                df_editor = pd.DataFrame(tabela_dados)
                df_editado = st.data_editor(
                    df_editor,
                    column_config={
                        "aluno_id": None,
                        "Chamada": st.column_config.TextColumn("Chamada", disabled=True),
                        "Aluno": st.column_config.TextColumn("Aluno", disabled=True),
                        "Parcial": st.column_config.TextColumn("Parcial"),
                        "Diversificada": st.column_config.TextColumn("Diversificada"),
                        "Trimestral": st.column_config.TextColumn("Trimestral"),
                    },
                    hide_index=True,
                    width="stretch",
                    key="editor_notas_lote"
                )
                
                if st.button("Salvar Notas da Tabela"):
                    erros_validacao = []
                    dados_processados = []
                    
                    for _, row in df_editado.iterrows():
                        al_id = int(row['aluno_id'])
                        al_nome = row['Aluno']
                        
                        def converter_valor_texto(val):
                            if pd.isna(val) or str(val).strip() == "":
                                return 0.0
                            val_str = str(val).replace(',', '.').strip()
                            try:
                                return round(float(val_str), 1)
                            except:
                                return 0.0

                        p = converter_valor_texto(row['Parcial'])
                        d = converter_valor_texto(row['Diversificada'])
                        t = converter_valor_texto(row['Trimestral'])
                        
                        final_calc, errs = validar_e_calcular_notas(p, d, t)
                        if errs:
                            erros_validacao.append(f"Aluno **{al_nome}**: " + " | ".join(errs))
                        else:
                            dados_processados.append((al_id, p, d, t, final_calc))
                            
                    if erros_validacao:
                        st.error("Foram encontrados erros de validação nas notas informadas:")
                        for err in erros_validacao:
                            st.warning(err)
                        st.info("Nenhuma alteração foi salva devido a valores fora dos limites permitidos.")
                    else:
                        conexao = obter_conexao()
                        cursor = conexao.cursor()
                        cursor.execute("PRAGMA foreign_keys = ON;")
                        
                        for al_id, p, d, t, final_calc in dados_processados:
                            cursor.execute('DELETE FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_lote, al_id, disc_sel_id))
                            cursor.execute('''
                                INSERT INTO notas (periodo, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (periodo_lote, al_id, disc_sel_id, p, d, t, final_calc))
                            
                        conexao.commit()
                        conexao.close()
                        st.success(f"Notas da turma {turma_final_lote} validadas e salvas com sucesso!")

    elif sub_cadastro == "4. Cadastro Individual":
        st.subheader("Cadastro e Edição Manual de Registro Individual")
        
        periodo_form = st.selectbox("Período Letivo:", ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE"])
        
        df_turmas_cad = buscar_turmas()
        turmas_cad_lista = list(df_turmas_cad['nome_turma']) if not df_turmas_cad.empty else []
        opcoes_turma_cad = ["Selecione..."] + turmas_cad_lista + ["+ Nova Turma"]
        
        sel_turma_cad = st.selectbox("Turma:", opcoes_turma_cad)
        turma_final_cad = ""
        turma_id_cad = None
        
        if sel_turma_cad == "+ Nova Turma":
            turma_final_cad = st.text_input("Nome da Nova Turma (ex: 3ª SÉRIE A)").strip().upper()
        elif sel_turma_cad != "Selecione...":
            turma_final_cad = sel_turma_cad
            turma_id_cad = int(df_turmas_cad.loc[df_turmas_cad['nome_turma'] == turma_final_cad, 'id'].values[0])
            
        alunos_cad_lista = []
        if turma_id_cad:
            df_al_turma = buscar_alunos_da_turma_por_id(turma_id_cad)
            alunos_cad_lista = list(df_al_turma['nome_aluno']) if not df_al_turma.empty else []
            
        opcoes_aluno_cad = ["Selecione..."] + alunos_cad_lista + ["+ Novo Aluno"]
        sel_aluno_cad = st.selectbox("Aluno:", opcoes_aluno_cad)
        
        aluno_final_cad = ""
        if sel_aluno_cad == "+ Novo Aluno":
            aluno_final_cad = st.text_input("Nome do Novo Aluno").strip().upper()
        elif sel_aluno_cad != "Selecione...":
            aluno_final_cad = sel_aluno_cad
            
        df_disc_cad = buscar_disciplinas()
        disciplinas_cad_lista = list(df_disc_cad['nome_disciplina']) if not df_disc_cad.empty else []
        opcoes_disc_cad = ["Selecione..."] + disciplinas_cad_lista + ["+ Novo Componente"]
        
        sel_disc_cad = st.selectbox("Disciplina:", opcoes_disc_cad)
        disc_final_cad = ""
        if sel_disc_cad == "+ Novo Componente":
            disc_final_cad = st.text_input("Nome da Nova Disciplina").strip().upper()
        elif sel_disc_cad != "Selecione...":
            disc_final_cad = sel_disc_cad
            
        chamada_form = st.text_input("Número da Chamada")
        
        cfg = st.session_state.params_avaliacao
        with st.form("form_individual_limpo"):
            st.markdown(f"##### Notas (Limites: Parcial 0-{cfg['max_parcial']:.1f}, Diversificada 0-{cfg['max_diversificada']:.1f}, Trimestral 0-{cfg['max_trimestral']:.1f})")
            col_n1, col_n2, col_n3 = st.columns(3)
            with col_n1:
                n_parcial = st.number_input("Parcial", value=0.0, step=0.1, format="%.1f")
            with col_n2:
                n_diversificada = st.number_input("Diversificada", value=0.0, step=0.1, format="%.1f")
            with col_n3:
                n_trimestral = st.number_input("Avaliação", value=0.0, step=0.1, format="%.1f")
                
            n_final, lista_erros = validar_e_calcular_notas(n_parcial, n_diversificada, n_trimestral)
            st.markdown(f"**Nota Final Calculada (Somatória):** {n_final:.1f}")
                
            salvar_individual = st.form_submit_button("Salvar Registro")
            
            if salvar_individual:
                if lista_erros:
                    for err in lista_erros:
                        st.error(err)
                elif sel_turma_cad != "Selecione..." and sel_aluno_cad != "Selecione..." and sel_disc_cad != "Selecione..." and turma_final_cad and aluno_final_cad and disc_final_cad:
                    conexao = obter_conexao()
                    cursor = conexao.cursor()
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    
                    cursor.execute("INSERT OR IGNORE INTO turmas (nome_turma) VALUES (?)", (turma_final_cad,))
                    cursor.execute("SELECT id FROM turmas WHERE nome_turma = ?", (turma_final_cad,))
                    t_id = cursor.fetchone()[0]
                    
                    try:
                        chamada_clean = str(int(float(chamada_form))) if chamada_form else ""
                    except:
                        chamada_clean = chamada_form.strip()

                    cursor.execute("SELECT id FROM alunos WHERE nome_aluno = ? AND turma_id = ?", (aluno_final_cad, t_id))
                    aluno_res = cursor.fetchone()
                    if aluno_res:
                        aluno_id = aluno_res[0]
                        if chamada_clean:
                            cursor.execute("UPDATE alunos SET numero_chamada = ? WHERE id = ?", (chamada_clean, aluno_id))
                    else:
                        cursor.execute("INSERT INTO alunos (nome_aluno, numero_chamada, turma_id) VALUES (?, ?, ?)", (aluno_final_cad, chamada_clean, t_id))
                        aluno_id = cursor.lastrowid
                    
                    cursor.execute("INSERT OR IGNORE INTO disciplinas (nome_disciplina) VALUES (?)", (disc_final_cad,))
                    cursor.execute("SELECT id FROM disciplinas WHERE nome_disciplina = ?", (disc_final_cad,))
                    disciplina_id = cursor.fetchone()[0]
                    
                    cursor.execute('SELECT id FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_form, aluno_id, disciplina_id))
                    nota_res = cursor.fetchone()
                    
                    if nota_res:
                        cursor.execute('''
                            UPDATE notas 
                            SET nota_parcial = ?, nota_diversificada = ?, avaliacao_trimestral = ?, nota_final = ?
                            WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?
                        ''', (n_parcial, n_diversificada, n_trimestral, n_final, periodo_form, aluno_id, disciplina_id))
                        st.success("Registro atualizado com sucesso.")
                    else:
                        cursor.execute('''
                            INSERT INTO notas (periodo, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (periodo_form, aluno_id, disciplina_id, n_parcial, n_diversificada, n_trimestral, n_final))
                        st.success("Registro cadastrado com sucesso.")
                        
                    conexao.commit()
                    conexao.close()
                else:
                    st.error("Preencha todos os campos obrigatórios corretamente.")

    elif sub_cadastro == "5. Corrigir ou Unir Turmas":
        st.subheader("Correção de Nome de Turma")
        st.info("Use esta opção quando uma planilha for importada com o nome de turma errado. Se o novo nome for de uma turma que já existe, as duas serão unidas (alunos e notas), permitindo comparar os trimestres.")
        
        # Mostra a mensagem da última correção (o st.rerun apaga mensagens anteriores)
        if st.session_state.get("msg_turma"):
            st.success(st.session_state.msg_turma)
            st.session_state.msg_turma = None
        
        df_turmas_resumo = buscar_turmas_com_resumo()
        
        if df_turmas_resumo.empty:
            st.info("Nenhuma turma cadastrada.")
        else:
            st.markdown("##### Turmas Cadastradas")
            df_turmas_exibicao = df_turmas_resumo.drop(columns=['id']).rename(columns={
                'TURMA': 'Turma',
                'QTD_ALUNOS': 'Qtd. Alunos',
                'TRIMESTRES': 'Trimestres com Notas'
            })
            st.dataframe(df_turmas_exibicao, width="content", hide_index=True, height=altura_tabela(df_turmas_exibicao), column_config=centralizar(df_turmas_exibicao))
            
            lista_turmas_corrigir = ["Selecione..."] + list(df_turmas_resumo['TURMA'])
            turma_corrigir = st.selectbox("Turma que será corrigida:", lista_turmas_corrigir, key="turma_corrigir")
            
            if turma_corrigir != "Selecione...":
                turma_origem_id = int(df_turmas_resumo.loc[df_turmas_resumo['TURMA'] == turma_corrigir, 'id'].values[0])
                
                outras_turmas = [t for t in df_turmas_resumo['TURMA'] if t != turma_corrigir]
                opcoes_destino = ["Digitar novo nome..."] + outras_turmas
                destino_sel = st.selectbox("Novo nome da turma (ou turma existente para unir):", opcoes_destino, key="turma_destino")
                
                if destino_sel == "Digitar novo nome...":
                    novo_nome_turma = st.text_input("Digite o nome correto da turma:", key="novo_nome_turma").strip().upper()
                else:
                    novo_nome_turma = destino_sel
                
                if novo_nome_turma and novo_nome_turma != turma_corrigir:
                    if novo_nome_turma in outras_turmas:
                        turma_destino_id = int(df_turmas_resumo.loc[df_turmas_resumo['TURMA'] == novo_nome_turma, 'id'].values[0])
                        qtd_comum = contar_alunos_em_comum(turma_origem_id, turma_destino_id)
                        st.warning(
                            f"A turma **{turma_corrigir}** será **unida** à turma **{novo_nome_turma}**. "
                            f"Alunos com o mesmo nome nas duas turmas: **{qtd_comum}** (serão unificados). "
                            f"Se o mesmo aluno tiver nota no mesmo trimestre e disciplina nas duas, fica a nota da turma **{turma_corrigir}**."
                        )
                    else:
                        st.info(f"A turma **{turma_corrigir}** será renomeada para **{novo_nome_turma}**.")
                    
                    confirmar_correcao = st.checkbox("Confirmo a correção da turma", key="confirmar_correcao_turma")
                    if st.button("Aplicar Correção", type="primary", disabled=not confirmar_correcao):
                        try:
                            resultado = renomear_ou_unir_turma(turma_origem_id, novo_nome_turma)
                            if resultado == "unida":
                                st.session_state.msg_turma = f"Turma {turma_corrigir} unida à turma {novo_nome_turma} com sucesso!"
                            else:
                                st.session_state.msg_turma = f"Turma renomeada para {novo_nome_turma} com sucesso!"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao corrigir a turma: {e}")

    st.markdown("---")
    with st.expander("Gerenciamento do Banco de Dados"):
        if "confirmar_limpeza" not in st.session_state:
            st.session_state.confirmar_limpeza = False

        if not st.session_state.confirmar_limpeza:
            if st.button("Limpar Banco de Dados"):
                st.session_state.confirmar_limpeza = True
                st.rerun()
        else:
            st.warning("Tem certeza que deseja apagar todos os dados do banco?")
            col_sim, col_nao = st.columns(2)
            with col_sim:
                if st.button("Sim, apagar"):
                    deletar_banco()
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.success("Banco de dados limpo.")
                    components.html("<script>window.parent.location.reload();</script>", height=0)
            with col_nao:
                if st.button("Cancelar"):
                    st.session_state.confirmar_limpeza = False
                    st.rerun()
