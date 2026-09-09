import streamlit as st
import pandas as pd
import os
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
    atualizar_nota_por_id,
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

menu_principal = st.radio(
    "Módulo Principal:", 
    ["Consulta", "Cadastro"], 
    horizontal=True
)

st.markdown("---")

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
                                    df_exibicao = df_full[['DISCIPLINA', 'NOTA_PARCIAL', 'NOTA_DIVERSIFICADA', 'AVALIACAO_TRIMESTRAL', 'NOTA_FINAL']].rename(columns={
                                        'DISCIPLINA': 'Disciplina',
                                        'NOTA_PARCIAL': 'Nota Parcial',
                                        'NOTA_DIVERSIFICADA': 'Nota Diversificada',
                                        'AVALIACAO_TRIMESTRAL': 'Avaliação Trimestral',
                                        'NOTA_FINAL': 'Nota Final'
                                    })
                                    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
                                    
                                    st.markdown("---")
                                    alterar_notas = st.checkbox("Habilitar modo de alteração de notas")
                                    
                                    if alterar_notas:
                                        st.markdown("##### Editar Notas por Disciplina")
                                        for index, row in df_full.iterrows():
                                            with st.form(f"form_alt_{row['nota_id']}"):
                                                st.write(f"**Disciplina:** {row['DISCIPLINA']}")
                                                c_n1, c_n2, c_n3 = st.columns(3)
                                                with c_n1:
                                                    novo_parcial = st.number_input("Parcial", value=float(row['NOTA_PARCIAL'] or 0.0), step=0.1, format="%.2f", key=f"p_{row['nota_id']}")
                                                with c_n2:
                                                    novo_div = st.number_input("Diversificada", value=float(row['NOTA_DIVERSIFICADA'] or 0.0), step=0.1, format="%.2f", key=f"d_{row['nota_id']}")
                                                with c_n3:
                                                    novo_trim = st.number_input("Avaliação", value=float(row['AVALIACAO_TRIMESTRAL'] or 0.0), step=0.1, format="%.2f", key=f"t_{row['nota_id']}")
                                                
                                                salvar_alt = st.form_submit_button("Atualizar Nota")
                                                if salvar_alt:
                                                    atualizar_nota_por_id(row['nota_id'], novo_parcial, novo_div, novo_trim)
                                                    st.success(f"Nota de {row['DISCIPLINA']} atualizada com sucesso.")
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
        ["Importar Planilha (Lote)", "Lançamento em Lote (Componente)", "Cadastro Individual"], 
        horizontal=True
    )
    st.markdown("---")
    
    # ----------------------------------------------------
    # OPÇÃO A: IMPORTAR PLANILHA EM LOTE
    # ----------------------------------------------------
    if sub_cadastro == "Importar Planilha (Lote)":
        st.subheader("Importação em Lote via Planilha Excel")
        
        periodo_imp = st.selectbox("Período Letivo:", ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE"])
        arquivo_enviado = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])
        
        if arquivo_enviado is not None:
            if st.button("Processar e Inserir no Banco de Dados"):
                try:
                    nome_turma = os.path.splitext(arquivo_enviado.name)[0].replace("_", " ").upper()
                    temp_filename = f"temp_{arquivo_enviado.name}"
                    
                    with open(temp_filename, "wb") as f:
                        f.write(arquivo_enviado.getbuffer())
                    
                    xls = pd.ExcelFile(temp_filename)
                    
                    conexao = obter_conexao()
                    cursor = conexao.cursor()
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    
                    cursor.execute("INSERT OR IGNORE INTO turmas (nome_turma) VALUES (?)", (nome_turma,))
                    cursor.execute("SELECT id FROM turmas WHERE nome_turma = ?", (nome_turma,))
                    turma_id = cursor.fetchone()[0]
                    
                    for disciplina in xls.sheet_names:
                        cursor.execute("INSERT OR IGNORE INTO disciplinas (nome_disciplina) VALUES (?)", (disciplina.upper(),))
                        cursor.execute("SELECT id FROM disciplinas WHERE nome_disciplina = ?", (disciplina.upper(),))
                        disciplina_id = cursor.fetchone()[0]
                        
                        df = pd.read_excel(temp_filename, sheet_name=disciplina, header=None)
                        
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
                            
                            def converter_para_float(valor):
                                if pd.isna(valor):
                                    return 0.0
                                try:
                                    val_str = str(valor).replace(',', '.').strip()
                                    return float(val_str)
                                except:
                                    return 0.0

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
                                    nota_parcial = converter_para_float(val)
                                elif "DIVERSIFICADA" in nome_coluna:
                                    nota_diversificada = converter_para_float(val)
                                elif "TRIMESTRAL" in nome_coluna:
                                    avaliacao_trimestral = converter_para_float(val)
                                elif "TOTAL" in nome_coluna or col_idx == num_cols - 1:
                                    nota_final = converter_para_float(val)

                            if nota_final is None:
                                nota_final = nota_parcial + nota_diversificada + avaliacao_trimestral

                            try:
                                num_chamada_str = str(int(float(num_chamada)))
                            except:
                                num_chamada_str = str(num_chamada).strip()

                            cursor.execute('SELECT id FROM alunos WHERE nome_aluno = ? AND turma_id = ?', (nome_str, turma_id))
                            aluno_res = cursor.fetchone()
                            
                            if aluno_res:
                                aluno_id = aluno_res[0]
                                cursor.execute("UPDATE alunos SET numero_chamada = ? WHERE id = ?", (num_chamada_str, aluno_id))
                            else:
                                cursor.execute('INSERT INTO alunos (nome_aluno, numero_chamada, turma_id) VALUES (?, ?, ?)', (nome_str, num_chamada_str, turma_id))
                                aluno_id = cursor.lastrowid

                            cursor.execute('DELETE FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_imp, aluno_id, disciplina_id))
                            cursor.execute('''
                                INSERT INTO notas (periodo, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (periodo_imp, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final))

                    conexao.commit()
                    conexao.close()
                    
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                        
                    st.success("Planilha processada e importada com sucesso.")
                except Exception as e:
                    st.error(f"Erro ao processar planilha: {e}")

    # ----------------------------------------------------
    # OPÇÃO B: LANÇAMENTO EM LOTE POR COMPONENTE
    # ----------------------------------------------------
    elif sub_cadastro == "Lançamento em Lote (Componente)":
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
                st.markdown(f"##### Lançando notas para a turma **{turma_final_lote}** em **{disc_final_lote}**")
                st.info("💡 **Dica:** Você pode copiar colunas de notas no Excel e colar diretamente na tabela abaixo usando Ctrl+C e Ctrl+V.")
                
                tabela_dados = []
                for _, al in df_alunos_sala.iterrows():
                    al_id = al['id']
                    
                    conexao_n = obter_conexao()
                    cursor_n = conexao_n.cursor()
                    cursor_n.execute('SELECT nota_parcial, nota_diversificada, avaliacao_trimestral FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_lote, al_id, disc_sel_id))
                    res_nota = cursor_n.fetchone()
                    conexao_n.close()
                    
                    val_p = float(res_nota[0]) if res_nota and res_nota[0] is not None else 0.0
                    val_d = float(res_nota[1]) if res_nota and res_nota[1] is not None else 0.0
                    val_t = float(res_nota[2]) if res_nota and res_nota[2] is not None else 0.0
                    
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
                    conexao = obter_conexao()
                    cursor = conexao.cursor()
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    
                    for _, row in df_editado.iterrows():
                        al_id = int(row['aluno_id'])
                        
                        def converter_valor_texto(val):
                            if pd.isna(val) or str(val).strip() == "":
                                return 0.0
                            val_str = str(val).replace(',', '.').strip()
                            try:
                                return float(val_str)
                            except:
                                return 0.0

                        p = converter_valor_texto(row['Parcial'])
                        d = converter_valor_texto(row['Diversificada'])
                        t = converter_valor_texto(row['Trimestral'])
                        final_calc = p + d + t
                        
                        cursor.execute('DELETE FROM notas WHERE periodo = ? AND aluno_id = ? AND disciplina_id = ?', (periodo_lote, al_id, disc_sel_id))
                        cursor.execute('''
                            INSERT INTO notas (periodo, aluno_id, disciplina_id, nota_parcial, nota_diversificada, avaliacao_trimestral, nota_final)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (periodo_lote, al_id, disc_sel_id, p, d, t, final_calc))
                        
                    conexao.commit()
                    conexao.close()
                    st.success(f"Notas da turma {turma_final_lote} salvas com sucesso.")

    # ----------------------------------------------------
    # OPÇÃO C: CADASTRO INDIVIDUAL
    # ----------------------------------------------------
    elif sub_cadastro == "Cadastro Individual":
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
        
        with st.form("form_individual_limpo"):
            st.markdown("##### Notas e Nota Final (Campos limpos para preenchimento)")
            col_n1, col_n2, col_n3 = st.columns(3)
            with col_n1:
                n_parcial = st.number_input("Parcial", value=0.0, step=0.1, format="%.2f")
            with col_n2:
                n_diversificada = st.number_input("Diversificada", value=0.0, step=0.1, format="%.2f")
            with col_n3:
                n_trimestral = st.number_input("Avaliação", value=0.0, step=0.1, format="%.2f")
                
            n_final = n_parcial + n_diversificada + n_trimestral
            st.markdown(f"**Nota Final (Soma):** {n_final:.2f}")
                
            salvar_individual = st.form_submit_button("Salvar Registro")
            
            if salvar_individual:
                if sel_turma_cad != "Selecione..." and sel_aluno_cad != "Selecione..." and sel_disc_cad != "Selecione..." and turma_final_cad and aluno_final_cad and disc_final_cad:
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

    # --- GERENCIAMENTO DO BANCO DE DADOS (Exclusivo na aba de Cadastro) ---
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