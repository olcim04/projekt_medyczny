-- ===============================================
-- UTWORZENIE BAZY DANYCH
-- ===============================================
DROP DATABASE IF EXISTS projekt_medyczny;
CREATE DATABASE projekt_medyczny
CHARACTER SET utf8mb4
COLLATE utf8mb4_polish_ci;

USE projekt_medyczny;

-- ===============================================
-- TABELA: UŻYTKOWNIK
-- ===============================================
DROP TABLE IF EXISTS UZYTKOWNIK;
CREATE TABLE UZYTKOWNIK (
    id_uzytkownika INT AUTO_INCREMENT PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    specjalista ENUM('klinicysta', 'admin') NOT NULL
) ENGINE=InnoDB;

-- ===============================================
-- TABELA: PACJENT
-- ===============================================
DROP TABLE IF EXISTS PACJENT;
CREATE TABLE PACJENT (
    id_pacjenta INT AUTO_INCREMENT PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    data_urodzenia DATE NOT NULL,
    plec ENUM('M', 'K', 'Inna') NOT NULL,
    id_prowadzacego INT NOT NULL,
    nazwa_dokumentu VARCHAR(100),
    numer_dokumentu VARCHAR(50),
    FOREIGN KEY (id_prowadzacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
		ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ===============================================
-- TABELA: BADANIE
-- ===============================================
DROP TABLE IF EXISTS BADANIE;
CREATE TABLE BADANIE (
    id_badania INT AUTO_INCREMENT PRIMARY KEY,
    id_pacjenta INT NOT NULL,
    id_prowadzacego INT NOT NULL,
    id_wykonujacego INT,
    data_badania DATE NOT NULL,
    czas_trwania TIME NOT NULL,
    wynik_ogolny DECIMAL(5,2),
    wynik_R DECIMAL(5,2),
    wynik_G DECIMAL(5,2),
    wynik_B DECIMAL(5,2),
    FOREIGN KEY (id_pacjenta) REFERENCES PACJENT(id_pacjenta)
        ON UPDATE CASCADE,
    FOREIGN KEY (id_prowadzacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
        ON UPDATE CASCADE,
    FOREIGN KEY (id_wykonujacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ===============================================
-- DODATKOWA INFORMACJA O JEDNOSTKACH WYNIKÓW
-- ===============================================
DROP TABLE IF EXISTS USTAWIENIA_SYSTEMU;
CREATE TABLE USTAWIENIA_SYSTEMU (
    id_ustawienia INT AUTO_INCREMENT PRIMARY KEY,
    klucz VARCHAR(50) UNIQUE NOT NULL,
    wartosc VARCHAR(100) NOT NULL
);

-- Wstawienie informacji o jednostce wyników
INSERT INTO USTAWIENIA_SYSTEMU (klucz, wartosc)
VALUES ('jednostka_wynikow', 'procent');