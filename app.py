import streamlit as st
from web3 import Web3
import json
import os
from solcx import compile_standard, install_solc, get_installed_solc_versions, get_installable_solc_versions, set_solc_version
from packaging.version import Version

# Função para garantir que a versão necessária do solc está instalada
def ensure_solc_installed(version='0.8.26'):
    installed_versions = get_installed_solc_versions()
    installed_versions_str = [str(ver) for ver in installed_versions]
    
    if version not in installed_versions_str:
        installable_versions = get_installable_solc_versions()
        if version in installable_versions:
            st.info(f"Instalando a versão {version} do solc...")
            install_solc(version)
            st.success(f"Versão {version} do solc instalada com sucesso.")
        else:
            available_version = max(installable_versions)
            st.warning(f"A versão {version} do solc não está disponível. Instalando a versão {available_version} em vez disso.")
            install_solc(available_version)
            set_solc_version(available_version)
            st.success(f"Versão {available_version} do solc instalada com sucesso.")
    else:
        set_solc_version(version)

# Garantir que a versão específica do compilador Solidity está instalada
try:
    ensure_solc_installed('0.8.26')
except Exception as e:
    st.error(f"Erro ao garantir a instalação do solc: {e}")
    raise

# Configurar a conexão com o nó local do Ganache
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))

# Função para compilar o contrato
def compile_contract(files):
    sources = {}
    for path, content in files.items():
        normalized_path = os.path.normpath(path).replace("\\", "/")
        sources[normalized_path] = {'content': content}
    
    try:
        compiled_sol = compile_standard({
            'language': 'Solidity',
            'sources': sources,
            'settings': {
                'outputSelection': {
                    '*': {
                        '*': ['abi', 'evm.bytecode', 'metadata']
                    }
                }
            }
        }, allow_paths='.')
    except Exception as e:
        st.error(f"Erro durante a compilação: {e}")
        raise

    if not compiled_sol.get('contracts'):
        st.error(f"Compilação falhou. Detalhes: {compiled_sol}")
        raise ValueError("Compilação falhou: Nenhum contrato compilado")

    # Salvar contratos compilados no estado da sessão
    st.session_state['compiled_contracts'] = compiled_sol['contracts']

    # Procurar pelo contrato concreto a ser implantado
    for file_name, contracts in compiled_sol['contracts'].items():
        for contract_name, contract_data in contracts.items():
            abi = contract_data.get('abi')
            bytecode_info = contract_data.get('evm', {}).get('bytecode', {})
            bytecode = bytecode_info.get('object')
            if bytecode is None or bytecode == "":
                st.error(f"Bytecode não gerado para o contrato: {contract_name}")
                continue
            st.write(f"Verificando contrato: {contract_name} com bytecode de tamanho {len(bytecode)}")
            if abi and bytecode and len(bytecode) > 0:  # Verifica se o bytecode é válido
                st.write(f"Contrato encontrado para implantação: {contract_name}")
                return abi, bytecode, contract_name

    raise ValueError("Compilação falhou: Nenhum contrato concreto encontrado")

# Interface Streamlit
st.title("Deploy de Contratos Solidity")

# Upload dos arquivos .sol
uploaded_files = st.file_uploader("Escolha os arquivos Solidity (.sol)", type=["sol"], accept_multiple_files=True)

if uploaded_files:
    files = {}
    for uploaded_file in uploaded_files:
        file_path = os.path.join("contracts", uploaded_file.name)
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        files[file_path] = uploaded_file.getbuffer().tobytes().decode('utf-8')
    st.success("Arquivos carregados com sucesso")

    # Seleção da carteira
    accounts = w3.eth.accounts
    selected_account = st.selectbox("Selecione a conta para o deploy", accounts)

    contract_address = None
    abi = None

    # Compilar e fazer o deploy do contrato
    if st.button("Compilar e Deploy"):
        with st.spinner("Compilando o contrato..."):
            try:
                abi, bytecode, contract_name = compile_contract(files)
                st.success("Contrato compilado com sucesso")
                # Deploy do contrato
                contract = w3.eth.contract(abi=abi, bytecode=bytecode)
                tx_hash = contract.constructor().transact({'from': selected_account})
                tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                contract_address = tx_receipt.contractAddress
                st.success(f"Contrato {contract_name} implantado com sucesso: {contract_address}")
                st.session_state['contract_address'] = contract_address
                st.session_state['abi'] = abi
            except Exception as e:
                st.error(f"Erro ao compilar e implantar o contrato: {e}")
                st.error(f"Detalhes: {str(e)}")

# Exibir contratos compilados salvos no estado da sessão
compiled_contracts = st.session_state.get('compiled_contracts', None)
if compiled_contracts:
    with st.expander("Contratos compilados"):
        st.json(compiled_contracts)

# Interação com o contrato implantado
contract_address = st.session_state.get('contract_address', None)
abi = st.session_state.get('abi', None)

if contract_address and abi:
    st.subheader("Interagir com o contrato implantado")

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Listar funções disponíveis no contrato
    for func in contract.all_functions():
        func_name = func.function_identifier
        func_abi = func.abi
        inputs = func_abi['inputs']

        # Criar interface dinamicamente para cada função
        st.write(f"Função: {func_name}")
        input_values = []
        for input in inputs:
            input_type = input['type']
            input_name = input['name']
            key = f"{func_name}_{input_name}"
            if input_type == 'uint256':
                value = st.number_input(f"{input_name} ({input_type})", min_value=0, step=1, key=key)
            elif input_type == 'address':
                value = st.text_input(f"{input_name} ({input_type})", key=key)
            else:
                value = st.text_input(f"{input_name} ({input_type})", key=key)
            input_values.append(value)

        if st.button(f"Chamar {func_name}", key=func_name):
            try:
                if func_abi['stateMutability'] == 'view':
                    result = func(*input_values).call()
                    st.write(f"Resultado: {result}")
                else:
                    tx_hash = func(*input_values).transact({'from': selected_account})
                    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                    st.success(f"Função {func_name} chamada com sucesso, hash da transação: {tx_receipt.transactionHash.hex()}")
            except Exception as e:
                st.error(f"Erro ao chamar a função {func_name}: {e}")
