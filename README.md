# tornado_test_task
Реализовать серверное приложение на tornado. Приложение должно слушать на двух tcp-портах (8888 и 8889). По
первому порту оно должно принимать подключения и сообщения от подключенных клиентов ("источников").

Структура сообщения от источника:
*1 байт - header (всегда 0x01)
*2 байта - номер сообщения в пределах данного подключения (беззнаковое целое)
*8 байт - идентификатор источника (ascii-строка)
*1 байт - статус источника, (беззнаковое целое), возможные занчения: 0x01 -- IDLE, 0x02 -- ACTIVE, 0x03 --
RECHARGE
*1 байт - numfields, количество полей с данными (беззнаковое целое)
Затем, в соответствии со значением поля numfields, идёт несколько пар полей следующего вида:
*8 байт - имя поля (ascii-строка)
*4 байта - значение поля (беззнаковое целое)
*1 байт - побайтовый XOR от сообщения

Сервер приложения в ответ присылает сообщения следующего вида:
*1 байт - header. Если сообщение было обработано успешно - 0x11, в противном случае - 0x12
*2 байта - номер сообщения или 0x00 0x00, если разобрать сообщение не удалось
*1 байт - побайтовый XOR от сообщения (своего).

Всем подключенным клиентам ("слушателям") на порту 8889 приложение должно отправлять на каждое принятое от
источника сообщение сообщения в текстовом формате следующего вида: "[<идентификатор источника>] <Имя
поля> | <Значение>\r\n" (по одной строке на каждую пару "имя - значение" в сообщении от источника).

При подключении нового слушателя на порт 8889, приложение должно отправить ему список всех подключенных на
данный момент источников в формате:
[<идентификатор источника>] <номер последнего сообщения> | <статус (строка "IDLE", "ACTIVE" или
"RECHARGE")> | <время, прошедшее с момента получения последнего сообщения в целых миллисекундах>\r\n (по
одной строчке на каждый источник)
