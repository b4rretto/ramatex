CREATE DATABASE IF NOT EXISTS fabrica_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fabrica_db;

CREATE TABLE IF NOT EXISTS funcionarios (
    id_funcionario INT AUTO_INCREMENT PRIMARY KEY,
    codigo_login VARCHAR(50) NOT NULL UNIQUE,
    nome VARCHAR(255) NOT NULL,
    cargo VARCHAR(100),
    senha VARCHAR(255) NOT NULL, -- In a real app, store hashed passwords!
    tipo_usuario ENUM('socio', 'funcionario') NOT NULL DEFAULT 'funcionario'
);

CREATE TABLE IF NOT EXISTS maquinas (
    id_maquina INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(100),
    valor_hora DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS desenhos (
    id_desenho INT AUTO_INCREMENT PRIMARY KEY,
    id_funcionario INT NOT NULL,
    codigo_desenho VARCHAR(100) NOT NULL,
    nome_desenho VARCHAR(255) NOT NULL,
    cliente VARCHAR(255),
    quantidade_pecas INT DEFAULT 1,
    data_inicio DATETIME NOT NULL,
    data_fim DATETIME,
    tempo_comercial_segundos INT, -- Storing as seconds
    status ENUM('aberto', 'fechado') NOT NULL DEFAULT 'aberto',
    FOREIGN KEY (id_funcionario) REFERENCES funcionarios(id_funcionario) ON DELETE CASCADE -- Consider ON DELETE SET NULL or RESTRICT
    -- UNIQUE constraint to prevent re-opening the same drawing by the same user if it's already open
    -- This is a bit more complex to enforce directly here if you allow multiple open drawings per user.
    -- The application logic will handle this.
);

-- Optional: Create an initial 'socio' user for testing
-- Replace 'admin_code', 'Admin User', 'admin_password' with your desired values
INSERT INTO funcionarios (codigo_login, nome, cargo, senha, tipo_usuario)
VALUES ('1234', 'Sócio Admin', 'Sócio-Diretor', 'adminpass', 'socio')
ON DUPLICATE KEY UPDATE nome=VALUES(nome); -- Prevents error if already exists

INSERT INTO funcionarios (codigo_login, nome, cargo, senha, tipo_usuario)
Values('6456', 'Funcionario', 'Operador', '12345', 'Funcionario')
ON DUPLICATE KEY UPDATE nome=VALUES(nome); -- Prevents error if already exists

INSERT INTO funcionarios (codigo_login, nome, cargo, senha, tipo_usuario)
VALUES ('emp001', 'Funcionário Teste', 'Operador', 'emppass', 'funcionario')
ON DUPLICATE KEY UPDATE nome=VALUES(nome);