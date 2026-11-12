-- Schema for the unmanaged application models in app/models.py.
-- Run after Django migrations, which create auth_user and the other Django tables.
-- Every table is created only when absent; existing rows are never replaced.

CREATE TABLE IF NOT EXISTS UZYTKOWNIK (
    id_uzytkownika INT AUTO_INCREMENT PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    specjalista VARCHAR(10) NOT NULL,
    auth_user_id INT NULL UNIQUE,
    CONSTRAINT fk_uzytkownik_auth_user
        FOREIGN KEY (auth_user_id) REFERENCES auth_user(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS PACJENT (
    id_pacjenta INT AUTO_INCREMENT PRIMARY KEY,
    imie VARCHAR(50) NOT NULL,
    nazwisko VARCHAR(50) NOT NULL,
    data_urodzenia DATE NOT NULL,
    plec VARCHAR(5) NOT NULL DEFAULT 'Inna',
    id_prowadzacego INT NOT NULL,
    nazwa_dokumentu VARCHAR(100) NULL,
    numer_dokumentu VARCHAR(50) NULL,
    CONSTRAINT fk_pacjent_prowadzacy
        FOREIGN KEY (id_prowadzacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS BADANIE (
    id_badania INT AUTO_INCREMENT PRIMARY KEY,
    id_pacjenta INT NOT NULL,
    id_prowadzacego INT NOT NULL,
    id_wykonujacego INT NULL,
    data_badania DATE NOT NULL,
    czas_trwania TIME NOT NULL,
    wynik_ogolny DECIMAL(5,2) NULL,
    wynik_R DECIMAL(5,2) NULL,
    wynik_G DECIMAL(5,2) NULL,
    wynik_B DECIMAL(5,2) NULL,
    wyniki_json LONGTEXT NULL,
    test_type VARCHAR(50) NULL,
    CONSTRAINT fk_badanie_pacjent
        FOREIGN KEY (id_pacjenta) REFERENCES PACJENT(id_pacjenta)
        ON UPDATE CASCADE,
    CONSTRAINT fk_badanie_prowadzacy
        FOREIGN KEY (id_prowadzacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
        ON UPDATE CASCADE,
    CONSTRAINT fk_badanie_wykonujacy
        FOREIGN KEY (id_wykonujacego) REFERENCES UZYTKOWNIK(id_uzytkownika)
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS USTAWIENIA_SYSTEMU (
    id_ustawienia INT AUTO_INCREMENT PRIMARY KEY,
    klucz VARCHAR(50) NOT NULL UNIQUE,
    wartosc VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
