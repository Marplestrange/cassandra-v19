-- Billetterie, lot 9 : les billets en PDF joints au courriel de confirmation.
-- Le PDF n'est PAS stocké : il se refait à l'envoi, depuis la base (un billet réémis ou annulé entre-temps ne part pas avec l'ancien QR).
ALTER TABLE courriels ADD COLUMN joindre TEXT NOT NULL DEFAULT '';
