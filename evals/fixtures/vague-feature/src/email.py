"""Der einzige E-Mail-Kanal der Anwendung. Alles, was Nutzer per Mail
erreichen soll, geht über diese Klasse — es gibt keinen zweiten Versandweg.
"""


class EmailService:
    def __init__(self, smtp_client):
        self._smtp_client = smtp_client

    def send(self, to: str, subject: str, body: str) -> None:
        self._smtp_client.send(to=to, subject=subject, body=body)
