import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, time, timedelta, date 
import mysql.connector
import traceback
from decimal import Decimal 

# --- Variáveis Globais de Usuário Logado ---
current_user_id = None
current_user_type = None 
current_user_nome = None
historico_limpo_nesta_sessao = False 

# --- Variáveis Globais para Orçamento ---
maquinas_no_orcamento_atual = [] 

# --- Configurações do Banco de Dados ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',      # <<< Altere aqui
    'password': 'Gab@2018', # <<< Altere aqui
    'database': 'fabrica_db'
}

# --- Funções de Conexão e Query com o Banco de Dados ---
def db_connect():
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        return cnx
    except mysql.connector.Error as err:
        print(f"DEBUG: Erro ao conectar ao DB: {err}")
        messagebox.showerror("Erro de Banco de Dados", f"Não foi possível conectar ao MySQL: {err}")
        return None

def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False, get_last_id=False):
    cnx = db_connect()
    if not cnx:
        return None 
    cursor = cnx.cursor(dictionary=True if fetchone or fetchall else False)
    last_id = None
    try:
        # print(f"DEBUG QUERY: {query} PARAMS: {params}") 
        cursor.execute(query, params or ())
        if commit:
            cnx.commit()
            if get_last_id:
                last_id = cursor.lastrowid
                return (True, last_id) 
            return True 
        
        result = None
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        return result 

    except mysql.connector.Error as err:
        print(f"DEBUG: Erro ao executar query: {err}\nQuery: {query}\nParams: {params}")
        if cnx and cnx.is_connected() and commit: 
            try:
                cnx.rollback()
            except mysql.connector.Error as rb_err:
                print(f"DEBUG: Erro no rollback: {rb_err}")
        return False 
    finally:
        if cnx and cnx.is_connected(): 
            cursor.close()
            cnx.close()

# --- Funções Auxiliares de Tempo ---
def formatar_tempo_delta_segundos(total_seconds):
    if total_seconds is None: return "00:00:00"
    total_seconds = int(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def hhmmss_para_horas_decimais(tempo_str):
    if not tempo_str or tempo_str.count(':') != 2: return 0.0
    try:
        h, m, s = map(int, tempo_str.split(':'))
        return h + (m / 60.0) + (s / 3600.0)
    except ValueError: return 0.0

def calcular_tempo_comercial_segundos(inicio_dt, fim_dt):
    if not isinstance(inicio_dt, datetime) or not isinstance(fim_dt, datetime): return 0
    if fim_dt <= inicio_dt: return 0
    tempo_total_comercial_delta = timedelta()
    hora_inicio_comercial = time(8, 0, 0); hora_fim_comercial = time(18, 0, 0)
    hora_inicio_almoco = time(13, 0, 0); hora_fim_almoco = time(14, 0, 0)
    data_atual_iter = inicio_dt.date(); data_fim_iter = fim_dt.date()
    while data_atual_iter <= data_fim_iter:
        if data_atual_iter.weekday() >= 5: 
            data_atual_iter += timedelta(days=1); continue
        
        inicio_comercial_dia = datetime.combine(data_atual_iter, hora_inicio_comercial)
        fim_comercial_dia = datetime.combine(data_atual_iter, hora_fim_comercial)
        
        inicio_manha = inicio_comercial_dia
        fim_manha = datetime.combine(data_atual_iter, hora_inicio_almoco)
        
        inicio_tarde = datetime.combine(data_atual_iter, hora_fim_almoco)
        fim_tarde = fim_comercial_dia

        inicio_efetivo_manha = max(inicio_dt, inicio_manha)
        fim_efetivo_manha = min(fim_dt, fim_manha)
        if fim_efetivo_manha > inicio_efetivo_manha: 
            tempo_total_comercial_delta += (fim_efetivo_manha - inicio_efetivo_manha)
        
        inicio_efetivo_tarde = max(inicio_dt, inicio_tarde)
        fim_efetivo_tarde = min(fim_dt, fim_tarde)
        if fim_efetivo_tarde > inicio_efetivo_tarde: 
            tempo_total_comercial_delta += (fim_efetivo_tarde - inicio_efetivo_tarde)
            
        data_atual_iter += timedelta(days=1)
    return int(tempo_total_comercial_delta.total_seconds())

# --- Funções CRUD Funcionários (MySQL) ---
def adicionar_funcionario():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem adicionar funcionários.")
        return

    codigo_login = entry_func_codigo_login.get()
    nome = entry_func_nome.get()
    cargo = entry_func_cargo.get()
    senha = entry_func_senha.get()
    tipo_usuario = combo_func_tipo.get().lower()

    if not codigo_login or not nome or not senha or not tipo_usuario:
        messagebox.showerror("Erro", "Código de Login, Nome, Senha e Tipo são obrigatórios.")
        return
    if tipo_usuario not in ['socio', 'funcionario']:
        messagebox.showerror("Erro", "Tipo de usuário inválido. Use 'socio' ou 'funcionario'.")
        return

    print(f"DEBUG: Tentando adicionar funcionário com codigo_login: '{codigo_login}'")

    check_query = "SELECT id_funcionario FROM funcionarios WHERE codigo_login = %s"
    existing_user = execute_query(check_query, (codigo_login,), fetchone=True)
    
    if existing_user is False: 
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível verificar o código de login.")
        return
    if isinstance(existing_user, dict): 
        messagebox.showerror("Erro", f"O Código de Login '{codigo_login}' já está em uso.")
        return

    query = "INSERT INTO funcionarios (codigo_login, nome, cargo, senha, tipo_usuario) VALUES (%s, %s, %s, %s, %s)"
    resultado_insert = execute_query(query, (codigo_login, nome, cargo, senha, tipo_usuario), commit=True)

    if resultado_insert == True or (isinstance(resultado_insert, tuple) and resultado_insert[0] == True) :
        print("DEBUG: Funcionário inserido no DB. Atualizando treeview...")
        atualizar_treeview_funcionarios()
        atualizar_combobox_funcionarios_desenho()
        limpar_campos_funcionario()
        messagebox.showinfo("Sucesso", "Funcionário adicionado!")
    elif resultado_insert is False: 
        print("DEBUG: Falha ao inserir funcionário no DB (execute_query retornou False).")
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível adicionar o funcionário. Verifique os logs para detalhes.")
    else: 
        print("DEBUG: Falha ao inserir funcionário no DB (execute_query retornou None - erro de conexão).")
        pass


def atualizar_treeview_funcionarios():
    if 'tree_funcionarios' not in globals():
        print("DEBUG: tree_funcionarios não definido globalmente ainda em atualizar_treeview_funcionarios.")
        return
    print("DEBUG: Entrando em atualizar_treeview_funcionarios") 
    for i in tree_funcionarios.get_children():
        tree_funcionarios.delete(i)
    print("DEBUG: Treeview de funcionários limpa.") 
    funcionarios_db = execute_query("SELECT id_funcionario, codigo_login, nome, cargo, tipo_usuario FROM funcionarios ORDER BY nome", fetchall=True)
    if funcionarios_db and isinstance(funcionarios_db, list): 
        if len(funcionarios_db) > 0:
             print(f"DEBUG: {len(funcionarios_db)} funcionários encontrados no DB para atualizar treeview.") 
             for func in funcionarios_db:
                tree_funcionarios.insert("", "end", values=(func["id_funcionario"], func["codigo_login"], func["nome"], func["cargo"], func["tipo_usuario"]))
             print("DEBUG: Treeview de funcionários repopulada.") 
        else: 
            print("DEBUG: Nenhum funcionário encontrado no DB (lista vazia).")
    elif funcionarios_db is False: 
        print("DEBUG: Erro ao buscar funcionários do DB para atualizar treeview.")
    else: 
        print(f"DEBUG: Nenhum funcionário encontrado ou retorno inesperado de funcionarios_db: {funcionarios_db}")


def selecionar_funcionario(event):
    selected_item = tree_funcionarios.selection()
    if not selected_item: return
    item_values = tree_funcionarios.item(selected_item[0], 'values')

    entry_func_id.config(state='normal')
    entry_func_id.delete(0, tk.END); entry_func_id.insert(0, item_values[0])
    entry_func_id.config(state='readonly')

    entry_func_codigo_login.delete(0, tk.END); entry_func_codigo_login.insert(0, item_values[1])
    entry_func_nome.delete(0, tk.END); entry_func_nome.insert(0, item_values[2])
    entry_func_cargo.delete(0, tk.END); entry_func_cargo.insert(0, item_values[3])
    combo_func_tipo.set(item_values[4].capitalize())
    entry_func_senha.delete(0, tk.END)

def atualizar_funcionario_selecionado():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem atualizar funcionários.")
        return
    selected_item = tree_funcionarios.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione um funcionário para atualizar.")
        return

    func_id_str = entry_func_id.get()
    if not func_id_str: 
        messagebox.showerror("Erro", "ID do funcionário não encontrado nos campos.")
        return
    func_id = int(func_id_str)

    novo_codigo_login = entry_func_codigo_login.get()
    novo_nome = entry_func_nome.get()
    novo_cargo = entry_func_cargo.get()
    nova_senha = entry_func_senha.get()
    novo_tipo_usuario = combo_func_tipo.get().lower()

    if not novo_codigo_login or not novo_nome or not novo_tipo_usuario:
        messagebox.showerror("Erro", "Código de Login, Nome e Tipo são obrigatórios.")
        return

    valor_original_codigo_login = ""
    try:
        valor_original_codigo_login = tree_funcionarios.item(selected_item[0], 'values')[1]
    except IndexError:
        messagebox.showerror("Erro Interno", "Não foi possível obter o código de login original do funcionário selecionado.")
        return


    if novo_codigo_login != valor_original_codigo_login: 
        check_query = "SELECT id_funcionario FROM funcionarios WHERE codigo_login = %s AND id_funcionario != %s"
        existing_user = execute_query(check_query, (novo_codigo_login, func_id), fetchone=True)
        if existing_user is False:
            messagebox.showerror("Erro de Banco de Dados", "Não foi possível verificar o código de login para atualização.")
            return
        if isinstance(existing_user, dict):
            messagebox.showerror("Erro", f"O Código de Login '{novo_codigo_login}' já está em uso por outro funcionário.")
            return

    if nova_senha:
        query = "UPDATE funcionarios SET codigo_login=%s, nome=%s, cargo=%s, senha=%s, tipo_usuario=%s WHERE id_funcionario=%s"
        params = (novo_codigo_login, novo_nome, novo_cargo, nova_senha, novo_tipo_usuario, func_id)
    else:
        query = "UPDATE funcionarios SET codigo_login=%s, nome=%s, cargo=%s, tipo_usuario=%s WHERE id_funcionario=%s"
        params = (novo_codigo_login, novo_nome, novo_cargo, novo_tipo_usuario, func_id)

    resultado_update = execute_query(query, params, commit=True)
    if resultado_update == True:
        atualizar_treeview_funcionarios()
        atualizar_combobox_funcionarios_desenho()
        limpar_campos_funcionario()
        messagebox.showinfo("Sucesso", "Funcionário atualizado!")
    elif resultado_update is False:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível atualizar o funcionário.")


def deletar_funcionario_selecionado():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem deletar funcionários.")
        return
    selected_item = tree_funcionarios.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione um funcionário para deletar.")
        return
    
    func_id_str = entry_func_id.get()
    if not func_id_str:
        messagebox.showerror("Erro", "ID do funcionário não encontrado nos campos para deleção.") 
        return
    try:
        func_id = int(func_id_str)
    except ValueError:
        messagebox.showerror("Erro", "ID do funcionário inválido para deleção.")
        return

    if not messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar o funcionário ID {func_id}? Esta ação não pode ser desfeita e pode afetar desenhos associados."):
        return

    if func_id == current_user_id:
        messagebox.showerror("Erro", "Você não pode deletar a si mesmo.")
        return

    print(f"DEBUG: Tentando deletar funcionário ID: {func_id}") 
    query = "DELETE FROM funcionarios WHERE id_funcionario=%s"
    resultado_delete = execute_query(query, (func_id,), commit=True)
    print(f"DEBUG: Resultado da deleção do funcionário: {resultado_delete}") 

    if resultado_delete == True:
        print("DEBUG: Funcionário deletado do DB. Atualizando UI.") 
        atualizar_treeview_funcionarios()
        atualizar_combobox_funcionarios_desenho()
        limpar_campos_funcionario() 
        messagebox.showinfo("Sucesso", "Funcionário deletado!")
    else:
        print("DEBUG: Falha ao deletar funcionário do DB.") 
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível deletar o funcionário. Verifique os logs.")


def limpar_campos_funcionario():
    entry_func_id.config(state='normal'); entry_func_id.delete(0, tk.END); entry_func_id.config(state='readonly')
    entry_func_codigo_login.delete(0, tk.END)
    entry_func_nome.delete(0, tk.END)
    entry_func_cargo.delete(0, tk.END)
    entry_func_senha.delete(0, tk.END)
    combo_func_tipo.set("Funcionario")
    if tree_funcionarios.selection(): tree_funcionarios.selection_remove(tree_funcionarios.selection()[0])

# --- Funções CRUD Máquinas (MySQL) ---
def adicionar_maquina():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem adicionar máquinas.")
        return
    nome = entry_maq_nome.get()
    tipo = entry_maq_tipo.get()
    try:
        valor_hora = float(entry_maq_valor_hora.get())
    except ValueError:
        messagebox.showerror("Erro", "Valor/Hora deve ser um número.")
        return
    if not nome:
        messagebox.showerror("Erro", "Nome da máquina é obrigatório.")
        return

    query = "INSERT INTO maquinas (nome, tipo, valor_hora) VALUES (%s, %s, %s)"
    if execute_query(query, (nome, tipo, valor_hora), commit=True) == True:
        atualizar_treeview_maquinas()
        atualizar_combobox_maquinas_orcamento()
        limpar_campos_maquina()
        messagebox.showinfo("Sucesso", "Máquina adicionada!")
    else:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível adicionar a máquina.")


def atualizar_treeview_maquinas():
    if 'tree_maquinas' not in globals(): print("DEBUG: tree_maquinas não definido globalmente ainda."); return
    for i in tree_maquinas.get_children():
        tree_maquinas.delete(i)
    maquinas_db = execute_query("SELECT id_maquina, nome, tipo, valor_hora FROM maquinas ORDER BY nome", fetchall=True)
    if maquinas_db and isinstance(maquinas_db, list): 
        for maq in maquinas_db:
            tree_maquinas.insert("", "end", values=(maq["id_maquina"], maq["nome"], maq["tipo"], f"{maq['valor_hora']:.2f}"))
    elif maquinas_db is False:
        print("DEBUG: Erro ao buscar máquinas do DB.")


def selecionar_maquina(event):
    selected_item = tree_maquinas.selection()
    if not selected_item: return
    item_values = tree_maquinas.item(selected_item[0], 'values')
    entry_maq_id.config(state='normal')
    entry_maq_id.delete(0, tk.END); entry_maq_id.insert(0, item_values[0])
    entry_maq_id.config(state='readonly')
    entry_maq_nome.delete(0, tk.END); entry_maq_nome.insert(0, item_values[1])
    entry_maq_tipo.delete(0, tk.END); entry_maq_tipo.insert(0, item_values[2])
    entry_maq_valor_hora.delete(0, tk.END); entry_maq_valor_hora.insert(0, item_values[3])

def atualizar_maquina_selecionada():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem atualizar máquinas.")
        return
    selected_item = tree_maquinas.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione uma máquina para atualizar.")
        return
    
    maq_id_str = entry_maq_id.get()
    if not maq_id_str:
        messagebox.showerror("Erro", "ID da máquina não encontrado.")
        return
    maq_id = int(maq_id_str)
    
    novo_nome = entry_maq_nome.get()
    novo_tipo = entry_maq_tipo.get()
    try:
        novo_valor_hora = float(entry_maq_valor_hora.get())
    except ValueError:
        messagebox.showerror("Erro", "Valor/Hora deve ser um número.")
        return
    if not novo_nome:
        messagebox.showerror("Erro", "Nome da máquina é obrigatório.")
        return

    query = "UPDATE maquinas SET nome=%s, tipo=%s, valor_hora=%s WHERE id_maquina=%s"
    params = (novo_nome, novo_tipo, novo_valor_hora, maq_id)
    if execute_query(query, params, commit=True) == True:
        atualizar_treeview_maquinas()
        atualizar_combobox_maquinas_orcamento()
        limpar_campos_maquina()
        messagebox.showinfo("Sucesso", "Máquina atualizada!")
    else:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível atualizar a máquina.")


def deletar_maquina_selecionada():
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem deletar máquinas.")
        return
    selected_item = tree_maquinas.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione uma máquina para deletar.")
        return
    
    maq_id_str = entry_maq_id.get()
    if not maq_id_str:
        messagebox.showerror("Erro", "ID da máquina não encontrado para deleção.") 
        return
    try:
        maq_id = int(maq_id_str)
    except ValueError:
        messagebox.showerror("Erro", "ID da máquina inválido para deleção.")
        return

    if not messagebox.askyesno("Confirmar Deleção", f"Tem certeza que deseja deletar a máquina ID {maq_id}?"):
        return
    
    print(f"DEBUG: Tentando deletar máquina ID: {maq_id}") 
    query = "DELETE FROM maquinas WHERE id_maquina=%s"
    resultado_delete = execute_query(query, (maq_id,), commit=True)
    print(f"DEBUG: Resultado da deleção da máquina: {resultado_delete}") 

    if resultado_delete == True:
        print("DEBUG: Máquina deletada do DB. Atualizando UI.") 
        atualizar_treeview_maquinas()
        atualizar_combobox_maquinas_orcamento()
        limpar_campos_maquina() 
        messagebox.showinfo("Sucesso", "Máquina deletada!")
    else:
        print("DEBUG: Falha ao deletar máquina do DB.") 
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível deletar a máquina. Verifique os logs.")


def limpar_campos_maquina():
    entry_maq_id.config(state='normal'); entry_maq_id.delete(0, tk.END); entry_maq_id.config(state='readonly')
    entry_maq_nome.delete(0, tk.END)
    entry_maq_tipo.delete(0, tk.END)
    entry_maq_valor_hora.delete(0, tk.END)
    if tree_maquinas.selection(): tree_maquinas.selection_remove(tree_maquinas.selection()[0])


# --- Funções de Desenho (MySQL) ---
def atualizar_combobox_funcionarios_desenho():
    if 'combo_desenho_funcionario' not in globals(): print("DEBUG: combo_desenho_funcionario não definido globalmente ainda."); return
    if current_user_type == 'socio':
        funcionarios_db = execute_query("SELECT id_funcionario, nome FROM funcionarios ORDER BY nome", fetchall=True)
    else:
        funcionarios_db = execute_query("SELECT id_funcionario, nome FROM funcionarios WHERE id_funcionario = %s", (current_user_id,), fetchall=True)

    nomes_funcionarios = []
    if funcionarios_db and isinstance(funcionarios_db, list):
        nomes_funcionarios = [f"{f['nome']} (ID: {f['id_funcionario']})" for f in funcionarios_db]

    combo_desenho_funcionario['values'] = nomes_funcionarios
    if nomes_funcionarios:
        if current_user_type == 'funcionario':
            combo_desenho_funcionario.set(f"{current_user_nome} (ID: {current_user_id})")
            combo_desenho_funcionario.config(state='disabled')
        else:
            combo_desenho_funcionario.current(0)
            combo_desenho_funcionario.config(state='readonly')
    else:
        combo_desenho_funcionario.set('')
        combo_desenho_funcionario.config(state='disabled')


def abrir_desenho():
    funcionario_selecionado_str = combo_desenho_funcionario.get()
    codigo_desenho = entry_desenho_codigo.get()
    nome_desenho = entry_desenho_nome.get()
    cliente = entry_desenho_cliente.get()
    try:
        quantidade_pecas = int(entry_desenho_quantidade.get())
        if quantidade_pecas <= 0:
            messagebox.showerror("Erro", "Quantidade de peças deve ser um número positivo.")
            return
    except ValueError:
        messagebox.showerror("Erro", "Quantidade de peças deve ser um número inteiro.")
        return

    if not funcionario_selecionado_str or not codigo_desenho or not nome_desenho:
        messagebox.showerror("Erro", "Funcionário, Código e Nome do Desenho são obrigatórios.")
        return
    try:
        id_funcionario_desenho = int(funcionario_selecionado_str.split("(ID: ")[1][:-1])
    except:
        messagebox.showerror("Erro", "Funcionário inválido selecionado.")
        return

    check_query = "SELECT id_desenho FROM desenhos WHERE id_funcionario = %s AND codigo_desenho = %s AND status = 'aberto'"
    desenho_existente = execute_query(check_query, (id_funcionario_desenho, codigo_desenho), fetchone=True)
    if desenho_existente is False:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível verificar se o desenho já está aberto.")
        return
    if isinstance(desenho_existente, dict):
        messagebox.showwarning("Aviso", f"Desenho '{codigo_desenho}' já está aberto por este funcionário.")
        return

    data_inicio = datetime.now()
    query = """
        INSERT INTO desenhos (id_funcionario, codigo_desenho, nome_desenho, cliente, quantidade_pecas, data_inicio, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'aberto')
    """
    params = (id_funcionario_desenho, codigo_desenho, nome_desenho, cliente, quantidade_pecas, data_inicio)
    if execute_query(query, params, commit=True) == True:
        atualizar_treeview_desenhos_abertos() 
        entry_desenho_codigo.delete(0, tk.END)
        entry_desenho_nome.delete(0, tk.END)
        entry_desenho_cliente.delete(0, tk.END)
        entry_desenho_quantidade.delete(0, tk.END); entry_desenho_quantidade.insert(0, "1")
        messagebox.showinfo("Sucesso", f"Desenho '{codigo_desenho}' aberto.")
    else:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível abrir o desenho.")


def fechar_desenho_selecionado():
    selected_item = tree_desenhos_abertos.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione um desenho aberto para fechar.")
        return

    id_desenho_fechar = tree_desenhos_abertos.item(selected_item[0], 'values')[0]
    print(f"DEBUG: Tentando fechar desenho ID: {id_desenho_fechar}")

    desenho_info_query = "SELECT id_funcionario, data_inicio, codigo_desenho FROM desenhos WHERE id_desenho = %s AND status = 'aberto'"
    desenho_info = execute_query(desenho_info_query, (id_desenho_fechar,), fetchone=True)

    if desenho_info is False:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível buscar informações do desenho para fechar.")
        return
    if not isinstance(desenho_info, dict): 
        messagebox.showerror("Erro", "Desenho não encontrado ou já fechado (não é um dict).")
        return

    if current_user_type == 'funcionario' and desenho_info['id_funcionario'] != current_user_id:
        messagebox.showerror("Acesso Negado", "Você só pode fechar seus próprios desenhos.")
        return

    data_fim = datetime.now()
    data_inicio_dt = desenho_info["data_inicio"]
    tempo_com_seg = calcular_tempo_comercial_segundos(data_inicio_dt, data_fim)
    print(f"DEBUG: Desenho ID {id_desenho_fechar} - Data Início: {data_inicio_dt}, Data Fim: {data_fim}, Tempo Seg: {tempo_com_seg}")

    query_update_desenho = "UPDATE desenhos SET data_fim=%s, tempo_comercial_segundos=%s, status='fechado' WHERE id_desenho=%s"
    params_update = (data_fim, tempo_com_seg, id_desenho_fechar)
    print(f"DEBUG: Executando UPDATE para fechar desenho: {query_update_desenho} com params {params_update}")

    resultado_fechamento = execute_query(query_update_desenho, params_update, commit=True)
    print(f"DEBUG: Resultado da query de fechamento: {resultado_fechamento}")

    if resultado_fechamento == True:
        print("DEBUG: UPDATE do desenho bem-sucedido. Chamando atualizações de treeview...")
        atualizar_treeview_desenhos_abertos()
        atualizar_treeview_historico_desenhos() 
        if current_user_type == 'socio': 
            print("DEBUG: Usuário é sócio, atualizando combobox de orçamento.")
            atualizar_combobox_desenhos_orcamento()
        messagebox.showinfo("Sucesso", f"Desenho '{desenho_info['codigo_desenho']}' fechado.")
    else:
        print(f"DEBUG: Falha ao executar UPDATE para fechar desenho. Resultado: {resultado_fechamento}")
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível fechar o desenho (falha no UPDATE).")


def atualizar_treeview_desenhos_abertos(termo_pesquisa=""): 
    if 'tree_desenhos_abertos' not in globals(): print("DEBUG: tree_desenhos_abertos não definido globalmente ainda."); return
    for i in tree_desenhos_abertos.get_children():
        tree_desenhos_abertos.delete(i)
    
    base_query = """
        SELECT d.id_desenho, f.nome as funcionario_nome, d.codigo_desenho, d.nome_desenho, d.cliente, 
               d.quantidade_pecas, d.data_inicio
        FROM desenhos d
        JOIN funcionarios f ON d.id_funcionario = f.id_funcionario
        WHERE d.status = 'aberto'
    """
    params = []
    if termo_pesquisa:
        base_query += """ AND (d.codigo_desenho LIKE %s OR 
                               d.nome_desenho LIKE %s OR 
                               d.cliente LIKE %s OR 
                               f.nome LIKE %s)"""
        like_termo = f"%{termo_pesquisa}%"
        params.extend([like_termo, like_termo, like_termo, like_termo])
    
    base_query += " ORDER BY d.data_inicio DESC"
    
    desenhos_db = execute_query(base_query, tuple(params), fetchall=True)

    if desenhos_db and isinstance(desenhos_db, list):
        for d in desenhos_db:
            tree_desenhos_abertos.insert("", "end", values=(
                d["id_desenho"],
                d["funcionario_nome"],
                d["codigo_desenho"],
                d["nome_desenho"],
                d["cliente"],
                d["quantidade_pecas"],
                d["data_inicio"].strftime("%d/%m/%Y %H:%M:%S")
            ))
    elif desenhos_db is False:
        print("DEBUG: Erro ao buscar desenhos abertos.")

def pesquisar_desenhos_abertos():
    termo = entry_pesquisa_abertos.get()
    atualizar_treeview_desenhos_abertos(termo)


def atualizar_treeview_historico_desenhos(termo_pesquisa=""): 
    if 'tree_historico_desenhos' not in globals(): print("DEBUG: tree_historico_desenhos não definido globalmente ainda."); return
    print("DEBUG: Entrando em atualizar_treeview_historico_desenhos") 
    for i in tree_historico_desenhos.get_children():
        tree_historico_desenhos.delete(i)
    print("DEBUG: Treeview de histórico limpa.") 
    
    base_query = """
        SELECT d.id_desenho, f.nome as funcionario_nome, d.codigo_desenho, d.nome_desenho, d.cliente,
               d.quantidade_pecas, d.data_inicio, d.data_fim, d.tempo_comercial_segundos
        FROM desenhos d
        JOIN funcionarios f ON d.id_funcionario = f.id_funcionario
        WHERE d.status = 'fechado' 
    """
    params = []
    if termo_pesquisa:
        base_query += """ AND (d.codigo_desenho LIKE %s OR 
                               d.nome_desenho LIKE %s OR 
                               d.cliente LIKE %s OR 
                               f.nome LIKE %s)"""
        like_termo = f"%{termo_pesquisa}%"
        params.extend([like_termo, like_termo, like_termo, like_termo])

    base_query += " ORDER BY d.data_fim DESC"
    
    historico_db = execute_query(base_query, tuple(params), fetchall=True)

    if historico_db and isinstance(historico_db, list):
        print(f"DEBUG: {len(historico_db)} desenhos encontrados no histórico para atualizar treeview.") 
        for hist in historico_db:
            tree_historico_desenhos.insert("", "end", values=(
                hist["id_desenho"],
                hist["funcionario_nome"],
                hist["codigo_desenho"],
                hist["nome_desenho"],
                hist["cliente"],
                hist["quantidade_pecas"],
                hist["data_inicio"].strftime("%d/%m/%Y %H:%M:%S"),
                hist["data_fim"].strftime("%d/%m/%Y %H:%M:%S") if hist["data_fim"] else "N/A",
                formatar_tempo_delta_segundos(hist["tempo_comercial_segundos"])
            ))
        print("DEBUG: Treeview de histórico repopulada.") 
    elif historico_db is False:
        print("DEBUG: Erro ao buscar histórico de desenhos.")
    else: 
        print("DEBUG: Nenhum desenho encontrado no histórico ou lista vazia.")

def pesquisar_desenhos_historico():
    termo = entry_pesquisa_historico.get()
    atualizar_treeview_historico_desenhos(termo)


def deletar_desenho_historico_selecionado(): 
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem deletar desenhos do histórico.")
        return

    selected_item = tree_historico_desenhos.selection()
    if not selected_item:
        messagebox.showerror("Erro", "Selecione um desenho do histórico para deletar.")
        return

    if not messagebox.askyesno("Confirmar Deleção", 
                               "Tem certeza que deseja deletar permanentemente este desenho do histórico? Esta ação não pode ser desfeita."):
        return

    try:
        id_desenho_deletar = tree_historico_desenhos.item(selected_item[0], 'values')[0]
        print(f"DEBUG: Tentando deletar desenho do histórico ID: {id_desenho_deletar}")
    except IndexError:
        messagebox.showerror("Erro Interno", "Não foi possível obter o ID do desenho selecionado.")
        return
    except Exception as e: 
        messagebox.showerror("Erro Interno", f"Erro ao processar seleção da treeview: {e}")
        return


    query = "DELETE FROM desenhos WHERE id_desenho = %s AND status = 'fechado'"
    resultado_delete = execute_query(query, (id_desenho_deletar,), commit=True)
    print(f"DEBUG: Resultado da deleção do desenho do histórico: {resultado_delete}") 

    if resultado_delete == True:
        print(f"DEBUG: Desenho ID {id_desenho_deletar} deletado do histórico.")
        atualizar_treeview_historico_desenhos()
        atualizar_combobox_desenhos_orcamento() 
        messagebox.showinfo("Sucesso", "Desenho deletado do histórico.")
    else:
        print(f"DEBUG: Falha ao deletar desenho do histórico ID: {id_desenho_deletar}. Resultado: {resultado_delete}")
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível deletar o desenho do histórico.")

def limpar_historico_antigo_automaticamente(): 
    global historico_limpo_nesta_sessao
    if historico_limpo_nesta_sessao: 
        print("DEBUG: Limpeza automática de histórico já executada nesta sessão.")
        return

    print("DEBUG: Verificando histórico antigo para limpeza automática (60 dias).")
    try:
        data_limite = date.today() - timedelta(days=60)
        data_limite_str = data_limite.strftime('%Y-%m-%d %H:%M:%S') 
        
        count_query = "SELECT COUNT(*) as count FROM desenhos WHERE status = 'fechado' AND data_fim < %s"
        count_result = execute_query(count_query, (data_limite_str,), fetchone=True)
        
        num_to_delete = 0
        if count_result and isinstance(count_result, dict) and 'count' in count_result:
            num_to_delete = count_result['count']
        elif count_result is False:
            print("DEBUG: Erro ao contar desenhos para limpeza automática.")
            messagebox.showwarning("Aviso de Limpeza", "Não foi possível verificar o histórico antigo para limpeza automática devido a um erro no banco.")
            historico_limpo_nesta_sessao = True 
            return


        if num_to_delete > 0:
            if messagebox.askyesno("Limpeza Automática de Histórico", 
                                   f"{num_to_delete} desenhos concluídos há mais de 60 dias serão removidos do histórico. Deseja continuar?"):
                delete_query = "DELETE FROM desenhos WHERE status = 'fechado' AND data_fim < %s"
                resultado_delete = execute_query(delete_query, (data_limite_str,), commit=True)
                
                if resultado_delete == True:
                    print(f"DEBUG: {num_to_delete} desenhos antigos deletados do histórico.")
                    messagebox.showinfo("Limpeza Automática", f"{num_to_delete} desenhos antigos foram removidos do histórico.")
                    atualizar_treeview_historico_desenhos()
                    atualizar_combobox_desenhos_orcamento()
                else:
                    messagebox.showerror("Erro de Limpeza", "Não foi possível remover os desenhos antigos do histórico.")
            else:
                print("DEBUG: Limpeza automática de histórico cancelada pelo usuário.")
        else:
            print("DEBUG: Nenhum desenho antigo (60+ dias) encontrado para limpeza.")
            
        historico_limpo_nesta_sessao = True 
    except Exception as e:
        print(f"ERRO na limpeza automática de histórico: {e}")
        traceback.print_exc()
        historico_limpo_nesta_sessao = True 


# --- Funções de Orçamento (MySQL) ---
def atualizar_combobox_maquinas_orcamento(): 
    if 'combo_orc_maquina_selecao' not in globals(): print("DEBUG: combo_orc_maquina_selecao não definido globalmente ainda."); return
    maquinas_db = execute_query("SELECT id_maquina, nome FROM maquinas ORDER BY nome", fetchall=True)
    nomes_maquinas = []
    if maquinas_db and isinstance(maquinas_db, list):
        nomes_maquinas = [f"{m['nome']} (ID: {m['id_maquina']})" for m in maquinas_db]
    combo_orc_maquina_selecao['values'] = nomes_maquinas 
    if nomes_maquinas: combo_orc_maquina_selecao.current(0)
    else: combo_orc_maquina_selecao.set('')

def atualizar_combobox_desenhos_orcamento():
    if 'combo_orc_desenho' not in globals(): print("DEBUG: combo_orc_desenho não definido globalmente ainda."); return
    print("DEBUG: Entrando em atualizar_combobox_desenhos_orcamento") 
    query = """
        SELECT id_desenho, codigo_desenho, nome_desenho, cliente, tempo_comercial_segundos, quantidade_pecas
        FROM desenhos
        WHERE status = 'fechado' AND tempo_comercial_segundos IS NOT NULL AND data_fim IS NOT NULL
        ORDER BY data_fim DESC
    """ 
    desenhos_hist_db = execute_query(query, fetchall=True)
    desenhos_formatados = []
    if desenhos_hist_db and isinstance(desenhos_hist_db, list):
        print(f"DEBUG Orçamento: {len(desenhos_hist_db)} desenhos encontrados para combobox de orçamento.") 
        for d in desenhos_hist_db:
            cliente_str = f" (Cliente: {d['cliente']})" if d.get('cliente') else ""
            tempo_str = formatar_tempo_delta_segundos(d['tempo_comercial_segundos'])
            desenhos_formatados.append(f"ID:{d['id_desenho']} | {d['codigo_desenho']} - {d['nome_desenho']}{cliente_str} | Peças: {d['quantidade_pecas']} | Tempo: {tempo_str}")
    elif desenhos_hist_db is False:
        print("DEBUG Orçamento: Erro ao buscar desenhos para combobox.") 
    else:
        print("DEBUG Orçamento: Nenhum desenho encontrado para combobox (lista vazia ou None).") 

    combo_orc_desenho['values'] = desenhos_formatados
    if desenhos_formatados: 
        combo_orc_desenho.current(0)
        on_desenho_orcamento_selected(None) 
    else: 
        combo_orc_desenho.set('')
        limpar_campos_orcamento_parcial() 


def on_desenho_orcamento_selected(event): 
    if 'combo_orc_desenho' not in globals(): return 
    selecionado_str = combo_orc_desenho.get()
    print(f"DEBUG Orçamento: on_desenho_orcamento_selected - '{selecionado_str}'") 
    if not selecionado_str: 
        lbl_orc_qtd_pecas_val.config(text="N/A")
        if 'entry_orc_tempo_uso_maquina' in globals(): entry_orc_tempo_uso_maquina.delete(0, tk.END)
        return

    try:
        id_desenho_orc = int(selecionado_str.split("ID:")[1].split(" |")[0].strip())
        desenho_data = execute_query(
            "SELECT tempo_comercial_segundos, quantidade_pecas FROM desenhos WHERE id_desenho = %s",
            (id_desenho_orc,), fetchone=True
        )
        if desenho_data is False:
             messagebox.showerror("Erro de Banco de Dados", "Não foi possível buscar dados do desenho para orçamento.")
             lbl_orc_qtd_pecas_val.config(text="Erro DB")
             return
        if not isinstance(desenho_data, dict): 
            messagebox.showerror("Erro", "Desenho não encontrado no histórico para orçamento.")
            lbl_orc_qtd_pecas_val.config(text="N/A")
            return

        tempo_segundos = desenho_data.get('tempo_comercial_segundos')
        quantidade_pecas_desenho = desenho_data.get('quantidade_pecas', 1) 

        horas_decimais_sugeridas = tempo_segundos / 3600.0 if tempo_segundos else 0.0
        
        if 'entry_orc_tempo_uso_maquina' in globals():
            entry_orc_tempo_uso_maquina.delete(0, tk.END)
            entry_orc_tempo_uso_maquina.insert(0, f"{horas_decimais_sugeridas:.2f}")
            
        lbl_orc_qtd_pecas_val.config(text=str(quantidade_pecas_desenho)) 
        print(f"DEBUG Orçamento: Tempo Sugerido (do desenho): {horas_decimais_sugeridas:.2f}, Qtd Peças: {quantidade_pecas_desenho}") 

    except Exception as e: 
        print(f"DEBUG Orçamento: Erro em on_desenho_orcamento_selected ao extrair dados: {e}")
        traceback.print_exc()
        lbl_orc_qtd_pecas_val.config(text="Erro")

def adicionar_maquina_ao_orcamento():
    global maquinas_no_orcamento_atual
    maquina_selecionada_str = combo_orc_maquina_selecao.get()
    try:
        tempo_uso_maq_str = entry_orc_tempo_uso_maquina.get()
        if not tempo_uso_maq_str:
            messagebox.showerror("Erro", "Informe o tempo de uso para esta máquina.")
            return
        tempo_uso = float(tempo_uso_maq_str)
        if tempo_uso < 0: # Permitir 0, mas não negativo
            messagebox.showerror("Erro", "Tempo de uso da máquina não pode ser negativo.")
            return
    except ValueError:
        messagebox.showerror("Erro", "Tempo de uso da máquina deve ser um número.")
        return

    if not maquina_selecionada_str:
        messagebox.showerror("Erro", "Selecione uma máquina para adicionar.")
        return

    try:
        id_maquina = int(maquina_selecionada_str.split("(ID: ")[1][:-1])
        nome_maquina = maquina_selecionada_str.split(" (ID:")[0]
    except:
        messagebox.showerror("Erro", "Seleção de máquina inválida.")
        return

    for maq_orc in maquinas_no_orcamento_atual:
        if maq_orc['id_maquina'] == id_maquina:
            messagebox.showwarning("Aviso", f"Máquina '{nome_maquina}' já foi adicionada ao orçamento.")
            return
            
    maq_data_db = execute_query("SELECT valor_hora FROM maquinas WHERE id_maquina = %s", (id_maquina,), fetchone=True)
    if not maq_data_db or not isinstance(maq_data_db, dict) or 'valor_hora' not in maq_data_db:
        messagebox.showerror("Erro", f"Não foi possível obter o valor/hora para a máquina '{nome_maquina}'.")
        return
    
    valor_hora_decimal = maq_data_db['valor_hora']
    try:
        valor_hora = float(valor_hora_decimal)
    except (TypeError, ValueError):
        messagebox.showerror("Erro", f"Valor/hora inválido ({valor_hora_decimal}) para a máquina '{nome_maquina}'.")
        return


    maquinas_no_orcamento_atual.append({
        'id_maquina': id_maquina,
        'nome_maquina': nome_maquina,
        'valor_hora': valor_hora,
        'tempo_uso_orc': tempo_uso
    })
    atualizar_treeview_maquinas_orcamento()
    entry_orc_tempo_uso_maquina.delete(0, tk.END) 
    print(f"DEBUG Orçamento: Máquina adicionada: {maquinas_no_orcamento_atual[-1]}")

def remover_maquina_do_orcamento():
    global maquinas_no_orcamento_atual
    selected_items_tv = tree_maquinas_orcamento.selection() 
    if not selected_items_tv:
        messagebox.showerror("Erro", "Selecione uma máquina da lista para remover.")
        return
    
    selected_item_id_tv = selected_items_tv[0] 
    
    valores_selecionados = tree_maquinas_orcamento.item(selected_item_id_tv, 'values')
    if not valores_selecionados:
        messagebox.showerror("Erro", "Não foi possível obter os dados da máquina selecionada na lista.")
        return
        
    nome_maquina_remover = valores_selecionados[0] 

    index_to_remove = -1
    for i, maq in enumerate(maquinas_no_orcamento_atual):
        if maq['nome_maquina'] == nome_maquina_remover:
            index_to_remove = i
            break
            
    if index_to_remove != -1:
        maq_removida = maquinas_no_orcamento_atual.pop(index_to_remove)
        print(f"DEBUG Orçamento: Máquina removida: {maq_removida}")
        atualizar_treeview_maquinas_orcamento()
    else:
        messagebox.showerror("Erro", "Não foi possível encontrar a máquina selecionada para remover da lista interna.")


def atualizar_treeview_maquinas_orcamento():
    if 'tree_maquinas_orcamento' not in globals(): print("DEBUG: tree_maquinas_orcamento não definido."); return
    for i in tree_maquinas_orcamento.get_children():
        tree_maquinas_orcamento.delete(i)
    
    for maq in maquinas_no_orcamento_atual:
        custo_maq = maq['tempo_uso_orc'] * maq['valor_hora']
        tree_maquinas_orcamento.insert("", "end", values=(
            maq['nome_maquina'], 
            f"{maq['tempo_uso_orc']:.2f}",
            f"R$ {maq['valor_hora']:.2f}",
            f"R$ {custo_maq:.2f}"
        ))

def calcular_orcamento():
    global maquinas_no_orcamento_atual
    if current_user_type != 'socio':
        messagebox.showerror("Acesso Negado", "Apenas sócios podem calcular orçamentos.")
        return
    print("DEBUG: Entrando em calcular_orcamento")

    desenho_selecionado_str = combo_orc_desenho.get()
    print(f"DEBUG Orçamento: Desenho Str: '{desenho_selecionado_str}'")

    try:
        valor_material_total_str = entry_orc_valor_material.get()
        if not valor_material_total_str:
            messagebox.showerror("Erro", "Valor do material não pode estar vazio.")
            return
        valor_material_total = float(valor_material_total_str)
    except ValueError:
        messagebox.showerror("Erro", "Valor do material deve ser um número válido.")
        return

    if not desenho_selecionado_str: 
        messagebox.showerror("Erro", "Selecione um desenho do histórico.")
        return
    if not maquinas_no_orcamento_atual: 
        messagebox.showerror("Erro", "Adicione pelo menos uma máquina ao orçamento.")
        return
        
    try:
        id_desenho_orc = int(desenho_selecionado_str.split("ID:")[1].split(" |")[0].strip())
        print(f"DEBUG Orçamento: ID Desenho: {id_desenho_orc}")
    except Exception as e:
        print(f"DEBUG Orçamento: Erro ao extrair ID do Desenho: {e}")
        messagebox.showerror("Erro", "Desenho inválido selecionado. Formato inesperado.")
        return

    desenho_data_orc = execute_query("SELECT quantidade_pecas FROM desenhos WHERE id_desenho = %s", (id_desenho_orc,), fetchone=True)
    print(f"DEBUG Orçamento: Desenho Data DB (para orçamento): {desenho_data_orc}")

    if desenho_data_orc is False:
        messagebox.showerror("Erro de Banco de Dados", "Não foi possível buscar dados do desenho para o orçamento (query falhou).")
        return
    if not isinstance(desenho_data_orc, dict): 
        messagebox.showerror("Erro", "Dados do desenho (para orçamento) não encontrados no banco de dados.")
        return

    quantidade_pecas = desenho_data_orc.get('quantidade_pecas')
    if quantidade_pecas is None or not isinstance(quantidade_pecas, int) or quantidade_pecas <= 0:
        messagebox.showwarning("Aviso", "Quantidade de peças inválida ou não encontrada para o desenho selecionado no orçamento. Usando 1 para cálculo.")
        lbl_orc_custo_por_peca_val.config(text="R$ N/A (Qtd Peças Inválida)")
        quantidade_pecas = 1 

    custo_maquina_acumulado = 0.0
    for maq_orc in maquinas_no_orcamento_atual:
        try:
            valor_hora_maq = float(maq_orc['valor_hora']) 
            tempo_uso_maq = float(maq_orc['tempo_uso_orc'])
            custo_maquina_acumulado += tempo_uso_maq * valor_hora_maq
        except (ValueError, TypeError) as e:
            messagebox.showerror("Erro Interno", f"Erro ao processar dados da máquina {maq_orc['nome_maquina']}: {e}")
            return
            
    custo_total_orcamento = custo_maquina_acumulado + valor_material_total
    custo_por_peca = custo_total_orcamento / quantidade_pecas if quantidade_pecas > 0 else 0

    print(f"DEBUG Orçamento: Custo Maquina Acumulado: {custo_maquina_acumulado}, Custo Material: {valor_material_total}, Custo Total: {custo_total_orcamento}, Qtd Peças: {quantidade_pecas}, Custo/Peça: {custo_por_peca}")

    lbl_orc_custo_maquina_val.config(text=f"R$ {custo_maquina_acumulado:.2f}") 
    lbl_orc_custo_material_val.config(text=f"R$ {valor_material_total:.2f}")
    lbl_orc_custo_total_val.config(text=f"R$ {custo_total_orcamento:.2f}")
    lbl_orc_qtd_pecas_val.config(text=str(quantidade_pecas)) 
    lbl_orc_custo_por_peca_val.config(text=f"R$ {custo_por_peca:.2f}")
    print("DEBUG: Labels de orçamento atualizados.")

def limpar_campos_orcamento_parcial(): 
    if 'lbl_orc_qtd_pecas_val' in globals() and lbl_orc_qtd_pecas_val.winfo_exists(): 
        lbl_orc_qtd_pecas_val.config(text="N/A")
    if 'entry_orc_tempo_uso_maquina' in globals() and entry_orc_tempo_uso_maquina.winfo_exists(): 
        entry_orc_tempo_uso_maquina.delete(0, tk.END)


def limpar_orcamento_completo():
    global maquinas_no_orcamento_atual
    maquinas_no_orcamento_atual = []
    if 'tree_maquinas_orcamento' in globals() and tree_maquinas_orcamento.winfo_exists(): 
        atualizar_treeview_maquinas_orcamento()
    if 'entry_orc_valor_material' in globals() and entry_orc_valor_material.winfo_exists(): 
        entry_orc_valor_material.delete(0, tk.END)
    if 'combo_orc_desenho' in globals() and combo_orc_desenho.winfo_exists(): 
        combo_orc_desenho.set('') 
    
    if 'lbl_orc_custo_maquina_val' in globals() and lbl_orc_custo_maquina_val.winfo_exists(): 
        lbl_orc_custo_maquina_val.config(text="R$ 0.00")
    if 'lbl_orc_custo_material_val' in globals() and lbl_orc_custo_material_val.winfo_exists(): 
        lbl_orc_custo_material_val.config(text="R$ 0.00")
    if 'lbl_orc_custo_total_val' in globals() and lbl_orc_custo_total_val.winfo_exists(): 
        lbl_orc_custo_total_val.config(text="R$ 0.00")
    if 'lbl_orc_qtd_pecas_val' in globals() and lbl_orc_qtd_pecas_val.winfo_exists(): 
        lbl_orc_qtd_pecas_val.config(text="N/A")
    if 'lbl_orc_custo_por_peca_val' in globals() and lbl_orc_custo_por_peca_val.winfo_exists(): 
        lbl_orc_custo_por_peca_val.config(text="R$ 0.00")
    if 'entry_orc_tempo_uso_maquina' in globals() and entry_orc_tempo_uso_maquina.winfo_exists(): 
        entry_orc_tempo_uso_maquina.delete(0, tk.END)


# --- Funções de Login ---
def attempt_login():
    global current_user_id, current_user_type, current_user_nome, login_window
    print("DEBUG: attempt_login chamada")
    codigo_login_val = entry_login_id.get()
    senha_val = entry_login_senha.get()

    if not codigo_login_val or not senha_val:
        messagebox.showerror("Login", "Código de Login e Senha são obrigatórios.")
        return

    query = "SELECT id_funcionario, nome, tipo_usuario FROM funcionarios WHERE codigo_login = %s AND senha = %s"
    user_data = execute_query(query, (codigo_login_val, senha_val), fetchone=True)

    if user_data is False: 
        messagebox.showerror("Erro de Login", "Não foi possível verificar as credenciais. Tente novamente.")
        return
    if isinstance(user_data, dict): 
        print(f"DEBUG: Login bem-sucedido para {user_data['nome']}")
        current_user_id = user_data['id_funcionario']
        current_user_type = user_data['tipo_usuario']
        current_user_nome = user_data['nome']
        print("DEBUG: Destruindo login_window")
        login_window.destroy()
        print("DEBUG: Chamando initialize_main_app")
        initialize_main_app()
    else: 
        print("DEBUG: Login falhou - usuário não encontrado ou senha incorreta")
        messagebox.showerror("Login Falhou", "Código de Login ou Senha inválidos.")
        entry_login_senha.delete(0, tk.END)

def show_login_window():
    global login_window, entry_login_id, entry_login_senha, root
    print("DEBUG: show_login_window chamada")
    login_window = tk.Toplevel(root)
    login_window.title("Login - Sistema Fabril")

    # login_window.transient(root) 
    # login_window.grab_set()      

    login_window.resizable(False, False)

    login_window.update_idletasks() 
    width = 350 
    height = 220 
    screen_width = login_window.winfo_screenwidth()
    screen_height = login_window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    login_window.geometry(f'{width}x{height}+{x}+{y}')
    print(f"DEBUG: login_window geometry set to: {width}x{height}+{x}+{y}")

    login_frame = ttk.Frame(login_window, padding="20 20 20 20")
    login_frame.pack(expand=True, fill="both")

    ttk.Label(login_frame, text="Código de Login:", font=('Segoe UI', 11)).pack(pady=(0,5))
    entry_login_id = ttk.Entry(login_frame, width=30, font=('Segoe UI', 11))
    entry_login_id.pack(pady=5)
    entry_login_id.focus()

    ttk.Label(login_frame, text="Senha:", font=('Segoe UI', 11)).pack(pady=(5,5))
    entry_login_senha = ttk.Entry(login_frame, width=30, show="*", font=('Segoe UI', 11))
    entry_login_senha.pack(pady=5)
    entry_login_senha.bind("<Return>", lambda event: attempt_login())

    ttk.Button(login_frame, text="Login", command=attempt_login, style="Accent.TButton", width=10).pack(pady=20)

    login_window.protocol("WM_DELETE_WINDOW", lambda: (print("DEBUG: Janela de login fechada pelo X"), root.destroy()))
    
    print("DEBUG: Escondendo root window (withdraw)")
    root.withdraw() 
    
    login_window.lift()
    login_window.attributes('-topmost', True)
    login_window.focus_force()
    login_window.attributes('-topmost', False)

    print("DEBUG: show_login_window concluída")


# --- Interface Gráfica Principal ---
def initialize_main_app():
    global root, notebook, tab_funcionarios, tab_maquinas, tab_desenhos, tab_orcamento, tab_historico_pesquisa 
    global combo_desenho_funcionario, btn_deletar_hist_geral 
    global frame_add_maquina_orc, btn_calcular_orc, btn_limpar_orc, entry_orc_valor_material
    try:
        print("DEBUG: Entrando em initialize_main_app")
        if not root.winfo_exists():
            print("DEBUG: Janela root não existe mais em initialize_main_app. Saindo.")
            return

        print("DEBUG: Mostrando root window (deiconify)")
        root.deiconify()
        root.title(f"Sistema Fabril (Usuário: {current_user_nome} - {current_user_type.capitalize()})")
        print("DEBUG: Título da janela principal definido.")

        if current_user_type == 'socio':
            limpar_historico_antigo_automaticamente() 


        if current_user_type == 'socio':
            print("DEBUG: Configurando para sócio")
            try: notebook.tab(tab_funcionarios, state='normal')
            except tk.TclError: print("DEBUG: Aba Funcionários não encontrada para mostrar.")
            try: notebook.tab(tab_maquinas, state='normal')
            except tk.TclError: print("DEBUG: Aba Máquinas não encontrada para mostrar.")
            try: notebook.tab(tab_orcamento, state='normal')
            except tk.TclError: print("DEBUG: Aba Orçamento não encontrada para mostrar.")
            try: notebook.tab(tab_historico_pesquisa, state='normal') 
            except tk.TclError: print("DEBUG: Aba Histórico e Pesquisa não encontrada para mostrar.")
            
            if 'combo_desenho_funcionario' in globals() and combo_desenho_funcionario.winfo_exists(): 
                combo_desenho_funcionario.config(state='readonly')
            if 'btn_deletar_hist_geral' in globals() and btn_deletar_hist_geral.winfo_exists() : 
                btn_deletar_hist_geral.config(state='normal') 
            
            if 'frame_add_maquina_orc' in globals() and frame_add_maquina_orc.winfo_exists():
                for child in frame_add_maquina_orc.winfo_children():
                    if hasattr(child, 'config') and 'state' in child.keys(): # Verifica se o widget tem 'state'
                        child.config(state='normal')
            if 'btn_calcular_orc' in globals() and btn_calcular_orc.winfo_exists(): btn_calcular_orc.config(state='normal')
            if 'btn_limpar_orc' in globals() and btn_limpar_orc.winfo_exists(): btn_limpar_orc.config(state='normal')
            if 'entry_orc_valor_material' in globals() and entry_orc_valor_material.winfo_exists(): entry_orc_valor_material.config(state='normal')


            print("DEBUG: [SÓCIO] Chamando atualizações...")
            atualizar_treeview_funcionarios()
            atualizar_treeview_maquinas()
            atualizar_combobox_maquinas_orcamento() 

        elif current_user_type == 'funcionario':
            print("DEBUG: Configurando para funcionário")
            try: notebook.hide(tab_funcionarios)
            except tk.TclError: print("DEBUG: Aba Funcionários não encontrada para esconder.")
            try: notebook.hide(tab_maquinas)
            except tk.TclError: print("DEBUG: Aba Máquinas não encontrada para esconder.")
            try: notebook.hide(tab_orcamento)
            except tk.TclError: print("DEBUG: Aba Orçamento não encontrada para esconder.")
            try: notebook.hide(tab_historico_pesquisa) 
            except tk.TclError: print("DEBUG: Aba Histórico e Pesquisa não encontrada para esconder.")
            
            if 'combo_desenho_funcionario' in globals() and combo_desenho_funcionario.winfo_exists(): 
                combo_desenho_funcionario.config(state='disabled')
            if 'btn_deletar_hist_geral' in globals() and btn_deletar_hist_geral.winfo_exists() : 
                btn_deletar_hist_geral.config(state='disabled') 
            
            if 'frame_add_maquina_orc' in globals() and frame_add_maquina_orc.winfo_exists():
                for child in frame_add_maquina_orc.winfo_children():
                    if hasattr(child, 'config') and 'state' in child.keys():
                        child.config(state='disabled')
            if 'btn_calcular_orc' in globals() and btn_calcular_orc.winfo_exists(): btn_calcular_orc.config(state='disabled')
            if 'btn_limpar_orc' in globals() and btn_limpar_orc.winfo_exists(): btn_limpar_orc.config(state='disabled')
            if 'entry_orc_valor_material' in globals() and entry_orc_valor_material.winfo_exists(): entry_orc_valor_material.config(state='disabled')


        print("DEBUG: [COMUM] Chamando atualizações...")
        atualizar_combobox_funcionarios_desenho()
        atualizar_treeview_desenhos_abertos() 
        atualizar_treeview_historico_desenhos() 
        
        if current_user_type == 'socio':
            try:
                if tab_orcamento.winfo_exists() and str(tab_orcamento) in map(str, notebook.tabs()) and notebook.tab(notebook.tabs().index(str(tab_orcamento)), "state") == "normal":
                    print("DEBUG: Aba Orçamento visível, atualizando combobox de desenhos para orçamento.")
                    atualizar_combobox_desenhos_orcamento() 
            except (tk.TclError, ValueError) as e: 
                print(f"DEBUG: Aba Orçamento não encontrada ou estado não pôde ser verificado para atualizar combobox. Erro: {e}")
                pass 

        print("DEBUG: initialize_main_app concluída")

    except Exception as e:
        print(f"ERRO CRÍTICO em initialize_main_app: {e}")
        traceback.print_exc()
        messagebox.showerror("Erro Crítico", f"Ocorreu um erro ao inicializar a aplicação: {e}\n\n{traceback.format_exc()}")
        if root and root.winfo_exists(): root.destroy()


def on_closing():
    print("DEBUG: on_closing chamada")
    if messagebox.askokcancel("Sair", "Tem certeza que deseja sair do sistema?"):
        print("DEBUG: Destruindo root em on_closing")
        if root and root.winfo_exists(): root.destroy()


# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    root = None 
    btn_deletar_hist_geral = None 
    entry_pesquisa_abertos = None 
    entry_pesquisa_historico = None 
    combo_orc_maquina_selecao = None 
    entry_orc_tempo_uso_maquina = None 
    tree_maquinas_orcamento = None 
    frame_add_maquina_orc = None 
    btn_calcular_orc = None 
    btn_limpar_orc = None 
    entry_orc_valor_material = None 
    
    lbl_orc_qtd_pecas_val = None
    lbl_orc_custo_maquina_val = None
    lbl_orc_custo_material_val = None
    lbl_orc_custo_total_val = None
    lbl_orc_custo_por_peca_val = None


    try:
        print("DEBUG: Iniciando __main__")
        root = tk.Tk()
        print("DEBUG: root = tk.Tk() criado")
        root.geometry("1200x900") 

        # --- ESTILOS ---
        style = ttk.Style()
        available_themes = style.theme_names()
        if 'clam' in available_themes: style.theme_use('clam')
        elif 'vista' in available_themes: style.theme_use('vista')
        elif 'xpnative' in available_themes: style.theme_use('xpnative')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TLabel', padding=3)
        style.configure('TButton', padding=(8, 4), font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background="#E8E8E8", relief="groove", padding=5)
        style.configure('Treeview', rowheight=25, font=('Segoe UI', 9))
        style.configure('TEntry', padding=5, font=('Segoe UI', 10))
        style.configure('TCombobox', padding=5, font=('Segoe UI', 10))
        style.configure('TLabelframe', padding=10)
        style.configure('TLabelframe.Label', font=('Segoe UI', 11, 'bold'), padding=(0,5,0,10), foreground="#333")
        style.configure('Red.TButton', foreground='white', background='#C00000', font=('Segoe UI', 10, 'bold'))
        style.map('Red.TButton', background=[('active', '#A00000')])
        style.configure('Accent.TButton', foreground='white', background='#0078D7', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#005A9E')])
        print("DEBUG: Estilos configurados")


        notebook = ttk.Notebook(root)
        print("DEBUG: Notebook criado")

        # --- DEFINIÇÃO DAS ABAS E WIDGETS PRINCIPAIS ---
        # --- Aba Funcionários ---
        tab_funcionarios = ttk.Frame(notebook, padding=10)
        frame_form_func = ttk.LabelFrame(tab_funcionarios, text="Detalhes do Funcionário")
        frame_form_func.pack(padx=5, pady=5, fill="x")
        ttk.Label(frame_form_func, text="ID Interno:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry_func_id = ttk.Entry(frame_form_func, width=10, state='readonly')
        entry_func_id.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frame_form_func, text="Código Login:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        entry_func_codigo_login = ttk.Entry(frame_form_func, width=25)
        entry_func_codigo_login.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_func, text="Nome:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        entry_func_nome = ttk.Entry(frame_form_func, width=40)
        entry_func_nome.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_func, text="Cargo:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry_func_cargo = ttk.Entry(frame_form_func, width=25)
        entry_func_cargo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_func, text="Senha:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        entry_func_senha = ttk.Entry(frame_form_func, width=25, show="*")
        entry_func_senha.grid(row=2, column=3, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_func, text="(Deixe em branco para não alterar)").grid(row=2, column=4, padx=5, pady=5, sticky="w", columnspan=2)
        ttk.Label(frame_form_func, text="Tipo:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        combo_func_tipo = ttk.Combobox(frame_form_func, values=["Funcionario", "Socio"], width=23, state="readonly")
        combo_func_tipo.set("Funcionario")
        combo_func_tipo.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        frame_form_func.columnconfigure(1, weight=1)
        frame_form_func.columnconfigure(3, weight=2)
        frame_botoes_func = ttk.Frame(frame_form_func)
        frame_botoes_func.grid(row=4, column=0, columnspan=5, pady=15)
        ttk.Button(frame_botoes_func, text="Adicionar", command=adicionar_funcionario, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_func, text="Atualizar", command=atualizar_funcionario_selecionado).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_func, text="Deletar", command=deletar_funcionario_selecionado, style="Red.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_func, text="Limpar Campos", command=limpar_campos_funcionario).pack(side=tk.LEFT, padx=5)
        frame_lista_func = ttk.LabelFrame(tab_funcionarios, text="Lista de Funcionários")
        frame_lista_func.pack(padx=5, pady=5, fill="both", expand=True)
        cols_func = ("id_db", "cod_login", "nome_func", "cargo_func", "tipo_usr")
        tree_funcionarios = ttk.Treeview(frame_lista_func, columns=cols_func, show="headings")
        tree_funcionarios.heading("id_db", text="ID DB"); tree_funcionarios.column("id_db", width=60, anchor="center")
        tree_funcionarios.heading("cod_login", text="Cód. Login"); tree_funcionarios.column("cod_login", width=100, anchor="w")
        tree_funcionarios.heading("nome_func", text="Nome"); tree_funcionarios.column("nome_func", width=250, anchor="w")
        tree_funcionarios.heading("cargo_func", text="Cargo"); tree_funcionarios.column("cargo_func", width=150, anchor="w")
        tree_funcionarios.heading("tipo_usr", text="Tipo"); tree_funcionarios.column("tipo_usr", width=100, anchor="w")
        tree_funcionarios.pack(fill="both", expand=True, side="left")
        tree_funcionarios.bind("<<TreeviewSelect>>", selecionar_funcionario)
        scrollbar_func = ttk.Scrollbar(frame_lista_func, orient="vertical", command=tree_funcionarios.yview)
        tree_funcionarios.configure(yscrollcommand=scrollbar_func.set); scrollbar_func.pack(side="right", fill="y")

        # --- Aba Máquinas ---
        tab_maquinas = ttk.Frame(notebook, padding=10)
        frame_form_maq = ttk.LabelFrame(tab_maquinas, text="Detalhes da Máquina")
        frame_form_maq.pack(padx=5, pady=5, fill="x")
        ttk.Label(frame_form_maq, text="ID DB:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry_maq_id = ttk.Entry(frame_form_maq, width=10, state='readonly')
        entry_maq_id.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frame_form_maq, text="Nome:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        entry_maq_nome = ttk.Entry(frame_form_maq, width=50)
        entry_maq_nome.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_maq, text="Tipo:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry_maq_tipo = ttk.Entry(frame_form_maq, width=50)
        entry_maq_tipo.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_form_maq, text="Valor/Hora (R$):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        entry_maq_valor_hora = ttk.Entry(frame_form_maq, width=15)
        entry_maq_valor_hora.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        frame_form_maq.columnconfigure(1, weight=1)
        frame_botoes_maq = ttk.Frame(frame_form_maq)
        frame_botoes_maq.grid(row=4, column=0, columnspan=4, pady=15)
        ttk.Button(frame_botoes_maq, text="Adicionar", command=adicionar_maquina, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_maq, text="Atualizar", command=atualizar_maquina_selecionada).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_maq, text="Deletar", command=deletar_maquina_selecionada, style="Red.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_maq, text="Limpar Campos", command=limpar_campos_maquina).pack(side=tk.LEFT, padx=5)
        frame_lista_maq = ttk.LabelFrame(tab_maquinas, text="Lista de Máquinas")
        frame_lista_maq.pack(padx=5, pady=5, fill="both", expand=True)
        cols_maq = ("id_maq_db", "nome_maq", "tipo_maq", "valor_h_maq")
        tree_maquinas = ttk.Treeview(frame_lista_maq, columns=cols_maq, show="headings")
        tree_maquinas.heading("id_maq_db", text="ID DB"); tree_maquinas.column("id_maq_db", width=60, anchor="center")
        tree_maquinas.heading("nome_maq", text="Nome"); tree_maquinas.column("nome_maq", width=250, anchor="w")
        tree_maquinas.heading("tipo_maq", text="Tipo"); tree_maquinas.column("tipo_maq", width=150, anchor="w")
        tree_maquinas.heading("valor_h_maq", text="Valor/Hora"); tree_maquinas.column("valor_h_maq", width=100, anchor="e")
        tree_maquinas.pack(fill="both", expand=True, side="left")
        tree_maquinas.bind("<<TreeviewSelect>>", selecionar_maquina)
        scrollbar_maq = ttk.Scrollbar(frame_lista_maq, orient="vertical", command=tree_maquinas.yview)
        tree_maquinas.configure(yscrollcommand=scrollbar_maq.set); scrollbar_maq.pack(side="right", fill="y")

        # --- Aba Controle de Desenhos ---
        tab_desenhos = ttk.Frame(notebook, padding=10)
        
        frame_abrir_desenho = ttk.LabelFrame(tab_desenhos, text="Abrir/Fechar Desenho")
        frame_abrir_desenho.pack(padx=5, pady=5, fill="x", side="top") 
        ttk.Label(frame_abrir_desenho, text="Funcionário:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        combo_desenho_funcionario = ttk.Combobox(frame_abrir_desenho, width=40, state="readonly")
        combo_desenho_funcionario.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_abrir_desenho, text="Código Desenho:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        entry_desenho_codigo = ttk.Entry(frame_abrir_desenho, width=40)
        entry_desenho_codigo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_abrir_desenho, text="Nome Desenho:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry_desenho_nome = ttk.Entry(frame_abrir_desenho, width=40)
        entry_desenho_nome.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_abrir_desenho, text="Cliente:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        entry_desenho_cliente = ttk.Entry(frame_abrir_desenho, width=40)
        entry_desenho_cliente.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(frame_abrir_desenho, text="Qtd. Peças:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        entry_desenho_quantidade = ttk.Entry(frame_abrir_desenho, width=10)
        entry_desenho_quantidade.insert(0, "1")
        entry_desenho_quantidade.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        frame_abrir_desenho.columnconfigure(1, weight=1)
        frame_botoes_desenho = ttk.Frame(frame_abrir_desenho)
        frame_botoes_desenho.grid(row=5, column=0, columnspan=2, pady=15)
        ttk.Button(frame_botoes_desenho, text="Abrir Desenho", command=abrir_desenho, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_desenho, text="Fechar Selecionado", command=fechar_desenho_selecionado).pack(side=tk.LEFT, padx=5)

        frame_pesquisa_abertos = ttk.LabelFrame(tab_desenhos, text="Pesquisar Desenhos em Aberto")
        frame_pesquisa_abertos.pack(padx=5, pady=5, fill="x", side="top")
        ttk.Label(frame_pesquisa_abertos, text="Termo:").pack(side=tk.LEFT, padx=5)
        entry_pesquisa_abertos = ttk.Entry(frame_pesquisa_abertos, width=40)
        entry_pesquisa_abertos.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        btn_pesquisar_abertos = ttk.Button(frame_pesquisa_abertos, text="Pesquisar", command=pesquisar_desenhos_abertos)
        btn_pesquisar_abertos.pack(side=tk.LEFT, padx=5)
        btn_limpar_pesquisa_abertos = ttk.Button(frame_pesquisa_abertos, text="Limpar", command=lambda: (entry_pesquisa_abertos.delete(0, tk.END), pesquisar_desenhos_abertos()))
        btn_limpar_pesquisa_abertos.pack(side=tk.LEFT, padx=5)
        
        frame_desenhos_abertos = ttk.LabelFrame(tab_desenhos, text="Desenhos em Aberto")
        frame_desenhos_abertos.pack(padx=5, pady=5, fill="both", expand=True, side="top") 
        
        cols_des_abertos = ("id_des", "func_aberto", "cod_des", "nome_des", "cli_des", "qtd_pecas_des", "inicio_des")
        tree_desenhos_abertos = ttk.Treeview(frame_desenhos_abertos, columns=cols_des_abertos, show="headings")
        tree_desenhos_abertos.heading("id_des", text="ID"); tree_desenhos_abertos.column("id_des", width=40, anchor="center", stretch=tk.NO)
        tree_desenhos_abertos.heading("func_aberto", text="Funcionário"); tree_desenhos_abertos.column("func_aberto", width=150, anchor="w")
        tree_desenhos_abertos.heading("cod_des", text="Cód. Desenho"); tree_desenhos_abertos.column("cod_des", width=100, anchor="w")
        tree_desenhos_abertos.heading("nome_des", text="Nome Desenho"); tree_desenhos_abertos.column("nome_des", width=200, anchor="w")
        tree_desenhos_abertos.heading("cli_des", text="Cliente"); tree_desenhos_abertos.column("cli_des", width=120, anchor="w")
        tree_desenhos_abertos.heading("qtd_pecas_des", text="Qtd Peças"); tree_desenhos_abertos.column("qtd_pecas_des", width=80, anchor="center")
        tree_desenhos_abertos.heading("inicio_des", text="Início"); tree_desenhos_abertos.column("inicio_des", width=140, anchor="center")
        tree_desenhos_abertos.pack(fill="both", expand=True, side="left", padx=5, pady=5) 
        scrollbar_des_abertos = ttk.Scrollbar(frame_desenhos_abertos, orient="vertical", command=tree_desenhos_abertos.yview)
        tree_desenhos_abertos.configure(yscrollcommand=scrollbar_des_abertos.set); scrollbar_des_abertos.pack(side="right", fill="y")
        

        # --- NOVA Aba Histórico e Pesquisa ---
        tab_historico_pesquisa = ttk.Frame(notebook, padding=10)

        frame_pesquisa_historico = ttk.LabelFrame(tab_historico_pesquisa, text="Pesquisar Histórico de Desenhos")
        frame_pesquisa_historico.pack(padx=5, pady=5, fill="x", side="top")
        ttk.Label(frame_pesquisa_historico, text="Termo:").pack(side=tk.LEFT, padx=5)
        entry_pesquisa_historico = ttk.Entry(frame_pesquisa_historico, width=40)
        entry_pesquisa_historico.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        btn_pesquisar_historico = ttk.Button(frame_pesquisa_historico, text="Pesquisar", command=pesquisar_desenhos_historico)
        btn_pesquisar_historico.pack(side=tk.LEFT, padx=5)
        btn_limpar_pesquisa_historico = ttk.Button(frame_pesquisa_historico, text="Limpar", command=lambda: (entry_pesquisa_historico.delete(0, tk.END), pesquisar_desenhos_historico()))
        btn_limpar_pesquisa_historico.pack(side=tk.LEFT, padx=5)

        frame_historico_view = ttk.LabelFrame(tab_historico_pesquisa, text="Histórico de Desenhos Concluídos")
        frame_historico_view.pack(padx=5, pady=5, fill="both", expand=True, side="top")
        
        cols_hist_des = ("id_hist", "func_hist", "cod_hist", "nome_hist", "cli_hist", "qtd_pecas_hist", "inicio_hist", "fim_hist", "tempo_com_hist")
        tree_historico_desenhos = ttk.Treeview(frame_historico_view, columns=cols_hist_des, show="headings")
        tree_historico_desenhos.heading("id_hist", text="ID"); tree_historico_desenhos.column("id_hist", width=40, anchor="center", stretch=tk.NO)
        tree_historico_desenhos.heading("func_hist", text="Funcionário"); tree_historico_desenhos.column("func_hist", width=150, anchor="w")
        tree_historico_desenhos.heading("cod_hist", text="Cód. Desenho"); tree_historico_desenhos.column("cod_hist", width=100, anchor="w")
        tree_historico_desenhos.heading("nome_hist", text="Nome Desenho"); tree_historico_desenhos.column("nome_hist", width=180, anchor="w")
        tree_historico_desenhos.heading("cli_hist", text="Cliente"); tree_historico_desenhos.column("cli_hist", width=120, anchor="w")
        tree_historico_desenhos.heading("qtd_pecas_hist", text="Qtd Peças"); tree_historico_desenhos.column("qtd_pecas_hist", width=80, anchor="center")
        tree_historico_desenhos.heading("inicio_hist", text="Início"); tree_historico_desenhos.column("inicio_hist", width=130, anchor="center")
        tree_historico_desenhos.heading("fim_hist", text="Fim"); tree_historico_desenhos.column("fim_hist", width=130, anchor="center")
        tree_historico_desenhos.heading("tempo_com_hist", text="Tempo Comercial"); tree_historico_desenhos.column("tempo_com_hist", width=110, anchor="center")
        tree_historico_desenhos.pack(fill="both", expand=True, side="left", padx=5, pady=5) 
        scrollbar_hist_des = ttk.Scrollbar(frame_historico_view, orient="vertical", command=tree_historico_desenhos.yview)
        tree_historico_desenhos.configure(yscrollcommand=scrollbar_hist_des.set); scrollbar_hist_des.pack(side="right", fill="y")

        btn_deletar_hist_geral = ttk.Button(tab_historico_pesquisa, text="Deletar Desenho Selecionado do Histórico", 
                                     command=deletar_desenho_historico_selecionado, style="Red.TButton")
        btn_deletar_hist_geral.pack(side="bottom", pady=10, fill="x", padx=5) 


        # --- Aba Orçamento ---
        tab_orcamento = ttk.Frame(notebook, padding=10)
        
        frame_orc_desenho_material = ttk.LabelFrame(tab_orcamento, text="Dados Base do Orçamento")
        frame_orc_desenho_material.pack(padx=5, pady=5, fill="x", side="top")

        ttk.Label(frame_orc_desenho_material, text="Selecionar Desenho (Histórico):").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        combo_orc_desenho = ttk.Combobox(frame_orc_desenho_material, width=60, state="readonly") 
        combo_orc_desenho.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        combo_orc_desenho.bind("<<ComboboxSelected>>", on_desenho_orcamento_selected)

        ttk.Label(frame_orc_desenho_material, text="Valor do Material Total (R$):").grid(row=1, column=0, padx=5, pady=8, sticky="w")
        entry_orc_valor_material = ttk.Entry(frame_orc_desenho_material, width=15)
        entry_orc_valor_material.grid(row=1, column=1, padx=5, pady=8, sticky="w")
        frame_orc_desenho_material.columnconfigure(1, weight=1)

        frame_add_maquina_orc = ttk.LabelFrame(tab_orcamento, text="Adicionar Máquinas ao Orçamento")
        frame_add_maquina_orc.pack(padx=5, pady=5, fill="x", side="top")
        
        ttk.Label(frame_add_maquina_orc, text="Máquina:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        combo_orc_maquina_selecao = ttk.Combobox(frame_add_maquina_orc, width=38, state="readonly")
        combo_orc_maquina_selecao.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(frame_add_maquina_orc, text="Tempo de Uso (horas):").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        entry_orc_tempo_uso_maquina = ttk.Entry(frame_add_maquina_orc, width=10)
        entry_orc_tempo_uso_maquina.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        btn_add_maq_orc = ttk.Button(frame_add_maquina_orc, text="Adicionar Máquina", command=adicionar_maquina_ao_orcamento)
        btn_add_maq_orc.grid(row=0, column=4, padx=10, pady=5, sticky="e")
        frame_add_maquina_orc.columnconfigure(1, weight=1) 

        frame_lista_maquinas_orc = ttk.LabelFrame(tab_orcamento, text="Máquinas no Orçamento Atual")
        frame_lista_maquinas_orc.pack(padx=5, pady=5, fill="both", expand=True, side="top")

        cols_maq_orc = ("nome", "tempo_uso", "valor_h", "custo_maq")
        tree_maquinas_orcamento = ttk.Treeview(frame_lista_maquinas_orc, columns=cols_maq_orc, show="headings", height=3) # Altura reduzida
        tree_maquinas_orcamento.heading("nome", text="Nome da Máquina")
        tree_maquinas_orcamento.heading("tempo_uso", text="Tempo Uso (h)")
        tree_maquinas_orcamento.heading("valor_h", text="Valor/Hora (R$)")
        tree_maquinas_orcamento.heading("custo_maq", text="Custo Máquina (R$)")
        tree_maquinas_orcamento.column("nome", width=250, anchor="w")
        tree_maquinas_orcamento.column("tempo_uso", width=100, anchor="center")
        tree_maquinas_orcamento.column("valor_h", width=120, anchor="e")
        tree_maquinas_orcamento.column("custo_maq", width=150, anchor="e")
        tree_maquinas_orcamento.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)
        scrollbar_maq_orc = ttk.Scrollbar(frame_lista_maquinas_orc, orient="vertical", command=tree_maquinas_orcamento.yview)
        tree_maquinas_orcamento.configure(yscrollcommand=scrollbar_maq_orc.set)
        scrollbar_maq_orc.pack(side=tk.RIGHT, fill="y")
        
        btn_rem_maq_orc = ttk.Button(frame_lista_maquinas_orc, text="Remover Selecionada", command=remover_maquina_do_orcamento, style="Red.TButton")
        btn_rem_maq_orc.pack(side=tk.BOTTOM, pady=5, padx=5, fill="x")


        frame_botoes_resultado_orc = ttk.Frame(tab_orcamento)
        frame_botoes_resultado_orc.pack(padx=5, pady=10, fill="x", side="top")

        btn_calcular_orc = ttk.Button(frame_botoes_resultado_orc, text="Calcular Orçamento Total", command=calcular_orcamento, style="Accent.TButton")
        btn_calcular_orc.pack(side=tk.LEFT, padx=10)
        btn_limpar_orc = ttk.Button(frame_botoes_resultado_orc, text="Limpar Orçamento", command=limpar_orcamento_completo)
        btn_limpar_orc.pack(side=tk.LEFT, padx=10)

        frame_resultado_orc = ttk.LabelFrame(tab_orcamento, text="Resultado do Orçamento")
        frame_resultado_orc.pack(padx=5, pady=5, fill="x", side="top") 
        lbl_font_orc = ('Segoe UI', 10) 
        lbl_val_font_orc = ('Segoe UI', 10, 'bold')
        lbl_total_font_orc = ('Segoe UI', 11, 'bold') 

        frame_resultado_orc.columnconfigure(1, weight=1) 

        ttk.Label(frame_resultado_orc, text="Qtd. Peças do Desenho:", font=lbl_font_orc).grid(row=0, column=0, padx=5, pady=3, sticky="w")
        lbl_orc_qtd_pecas_val = ttk.Label(frame_resultado_orc, text="N/A", font=lbl_val_font_orc, width=15, anchor="w") 
        lbl_orc_qtd_pecas_val.grid(row=0, column=1, padx=5, pady=3, sticky="ew")

        ttk.Label(frame_resultado_orc, text="Custo Total das Máquinas:", font=lbl_font_orc).grid(row=1, column=0, padx=5, pady=3, sticky="w")
        lbl_orc_custo_maquina_val = ttk.Label(frame_resultado_orc, text="R$ 0.00", font=lbl_val_font_orc, width=15, anchor="w")
        lbl_orc_custo_maquina_val.grid(row=1, column=1, padx=5, pady=3, sticky="ew")
        
        ttk.Label(frame_resultado_orc, text="Custo do Material (Total):", font=lbl_font_orc).grid(row=2, column=0, padx=5, pady=3, sticky="w")
        lbl_orc_custo_material_val = ttk.Label(frame_resultado_orc, text="R$ 0.00", font=lbl_val_font_orc, width=15, anchor="w")
        lbl_orc_custo_material_val.grid(row=2, column=1, padx=5, pady=3, sticky="ew")
        
        ttk.Separator(frame_resultado_orc, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
        
        ttk.Label(frame_resultado_orc, text="CUSTO TOTAL DO LOTE:", font=lbl_total_font_orc).grid(row=4, column=0, padx=5, pady=3, sticky="w")
        lbl_orc_custo_total_val = ttk.Label(frame_resultado_orc, text="R$ 0.00", font=lbl_total_font_orc, foreground="#0078D7", width=15, anchor="w")
        lbl_orc_custo_total_val.grid(row=4, column=1, padx=5, pady=3, sticky="ew")
        
        ttk.Label(frame_resultado_orc, text="CUSTO POR PEÇA:", font=lbl_total_font_orc).grid(row=5, column=0, padx=5, pady=3, sticky="w")
        lbl_orc_custo_por_peca_val = ttk.Label(frame_resultado_orc, text="R$ 0.00", font=lbl_total_font_orc, foreground="#0078D7", width=15, anchor="w")
        lbl_orc_custo_por_peca_val.grid(row=5, column=1, padx=5, pady=3, sticky="ew")
        print("DEBUG: Widgets das abas definidos")


        # Adicionar abas ao notebook.
        notebook.add(tab_funcionarios, text=" Funcionários ", state='hidden')
        notebook.add(tab_maquinas, text=" Máquinas ", state='hidden')
        notebook.add(tab_desenhos, text=" Controle de Desenhos ") 
        notebook.add(tab_historico_pesquisa, text=" Histórico e Pesquisa ", state='hidden') 
        notebook.add(tab_orcamento, text=" Orçamento ", state='hidden')
        print("DEBUG: Abas adicionadas ao notebook")

        notebook.pack(expand=True, fill="both", padx=10, pady=10)
        print("DEBUG: Notebook empacotado")

        root.protocol("WM_DELETE_WINDOW", on_closing)
        print("DEBUG: Protocolo WM_DELETE_WINDOW definido")

        show_login_window() 
        print("DEBUG: show_login_window retornou. Entrando em root.mainloop()")
        root.mainloop()
        print("DEBUG: root.mainloop() finalizado.")

    except Exception as e:
        print(f"ERRO FATAL no bloco __main__: {e}")
        traceback.print_exc()
        messagebox.showerror("Erro Fatal Inesperado", f"Ocorreu um erro fatal ao iniciar o programa: {e}\n\n{traceback.format_exc()}")
        if root and root.winfo_exists():
             try:
                 root.destroy()
             except tk.TclError:
                 pass
    finally:
        print("DEBUG: Fim do script.")