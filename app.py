import io
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
    DB_PATH
)

st.set_page_config(page_title="Painel de Desempenho Escolar", layout="centered")

st.title("Painel de Desempenho Escolar")

try:
    inicializar_banco()
except Exception as e:
    st.error(f"Erro ao inicializar o banco de dados: {e}")

# Gerencia no estado da sessão os valores máximos de cada critério
if "params_avaliacao" not in st.session_state:
    st.session_state.params_avaliacao = {
        "max_parcial": 3.0,
        "max_diversificada": 3.0,
        "max_trimestral": 4.0,
        "configurado": False
    }

if "importacao_pendente" not in st.session_state:
    st.session_state.importacao_pendente = None

menu_principal = st.radio(
    "Módulo Principal:", 
    ["Consulta", "Cadastro"], 
    horizontal=True
)

st.markdown("---")

# Função auxiliar para validar notas e calcular nota final por somatória simples
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
# MÓDULO 1: CONSULTA DE ALUNOS
# =========================================================================
if menu_principal == "Consulta":
    st.subheader("Consulta de Desempenho e Alteração de Notas")
    
    if os.path.exists(DB_PATH):
        try:
            df_periodos = buscar_periodos()
            
            if not df_periodos.empty:
                lista_periodos = ["Selecione..."] + list(df_periodos['periodo'])
                periodo_selecionado = st.selectbox("Período Letivo:", lista_periodos)
                
                if periodo_selecionado != "Selecione...":
                    df_turmas = buscar_turmas_por_periodo(periodo_selecionado)
                    
                    if not df_turmas.empty:
                        col1, col2 = st.columns(2)
                        with col1:
                            lista_turmas = ["Selecione..."] + list(df_turmas['nome_turma'])
                            turma_selecionada = st.selectbox("Turma:", lista_turmas)
                        
                        if turma_selecionada != "Selecione...":
                            df_alunos = buscar_alunos_por_turma(periodo_selecionado, turma_selecionada)
                            
                            with col2:
                                lista_alunos = ["Selecione..."] + list(df_alunos['nome_aluno'])
                                aluno_selecionado = st.selectbox("Aluno:", lista_alunos)

                            st.markdown("")
                            
                            if aluno_selecionado != "Selecione...":
                                df_full = buscar_notas_aluno_com_ids(periodo_selecionado, turma_selecionada, aluno_selecionado)
                                
                                if not df_full.empty:
                                    st.markdown("##### Boletim do Aluno")
                                    
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
                                    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
                                    
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
# MÓDULO 2: CADASTRO E LANÇAMENTOS
# =========================================================================
elif menu_principal == "Cadastro":
    sub_cadastro = st.radio(
        "Tipo de Cadastro / Lançamento:", 
        [
            "1. Definir Critérios e Limites (Obrigatório)", 
            "2. Importar Planilha (Lote)", 
            "3. Lançamento em Lote (Componente)", 
            "4. Cadastro Individual"
        ], 
        horizontal=False
    )
    st.markdown("---")
    
    # ----------------------------------------------------
    # ETAPA 1: DEFINIR CRITÉRIOS (OBRIGATÓRIO)
    # ----------------------------------------------------
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
                
            salvar_params = st.form_submit_button("Salvar Critérios e Ativar Lançamentos")
            
            if salvar_params:
                st.session_state.params_avaliacao = {
                    "max_parcial": max_parcial_input,
                    "max_diversificada": max_diversificada_input,
                    "max_trimestral": max_trimestral_input,
                    "configurado": True
                }
                st.success("Critérios salvos com sucesso! A nota final será a somatória simples dos instrumentos. Agora você já pode usar os lançamentos.")

        if st.session_state.params_avaliacao["configurado"]:
            st.success("Status: Critérios configurados e ativos no sistema.")
        else:
            st.warning("Você precisa salvar os critérios pelo menos uma vez antes de validar os lançamentos.")

    # ----------------------------------------------------
    # ETAPA 2: IMPORTAR PLANILHA EM LOTE (COM DETECÇÃO DE DUPLICIDADE)
    # ----------------------------------------------------
    elif sub_cadastro == "2. Importar Planilha (Lote)":
        st.subheader("Importação em Lote via Planilha Excel")
        
        periodo_imp = st.selectbox("Período Letivo:", ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE"])
        arquivo_enviado = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])
        
        if arquivo_enviado is not None:
            if st.button("Pré-analisar Planilha"):
                try:
                    nome_turma = os.path.splitext(arquivo_enviado.name)[0].replace("_", " ").upper()
                    
                    # Leitura segura via BytesIO para evitar WinError 32 no Windows
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

                            # Verifica se já existe registro idêntico no banco
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

        # Se houver uma pré-análise
        if st.session_state.importacao_pendente is not None:
            pendente = st.session_state.importacao_pendente
            qtd_validos = len(pendente["registros_validos"])
            df_erros = pendente["df_com_erro"]
            qtd_erros = len(df_erros)

            st.info(f"Resumo da Pré-análise (Turma: {pendente['nome_turma']} - {pendente['periodo']})")
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
                    use_container_width=True,
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
                            
                            nome_turma = pendente["nome_turma"]
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

    # ----------------------------------------------------
    # ETAPA 3: LANÇAMENTO EM LOTE POR COMPONENTE
    # ----------------------------------------------------
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
                    use_container_width=True,
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

    # ----------------------------------------------------
    # ETAPA 4: CADASTRO INDIVIDUAL
    # ----------------------------------------------------
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

    # --- GERENCIAMENTO DO BANCO DE DADOS ---
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