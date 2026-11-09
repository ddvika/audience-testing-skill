# Audience · отчёт для команды продукта

Синтетическое тестирование: ниже показаны план и фактически записанные прохождения AI-агентов. Их ответы не заменяют исследование реальных людей.

## Дизайн эксперимента

**Продукт:** Seatly · вымышленный сервис выбора билетов

**Задача:** Проверить путь от поиска события до понятного выбора билетов, без покупки. Это полностью вымышленный пример отчёта.

**Аудитория:** Вымышленные покупатели билетов с разными задачами и ограничениями.

**Почему выбрали её:** Проверяем разные задачи, опыт и устройства, чтобы увидеть, где путь к результату отличается. Это гипотезы аудитории по доступному интерфейсу, а не данные о реальных клиентах.

| Что считаем | Количество |
| --- | --- |
| Запланировано агентов | 6 |
| Агенты с записанными наблюдениями | 6 |
| Агенты с доступными для оценки результатами | 6 |
| Запланировано визитов | 8 |
| Визиты с записанными наблюдениями | 8 |
| Визиты с результатом для оценки | 8 |
| Блокировки | 0 |
| Ошибки инфраструктуры | 0 |
| Визиты без записанных наблюдений | 0 |

Режим изоляции не записан. Независимость аккаунтов и серверной памяти не подтверждена.

Подтверждённо запущено новых задач: 6. Продолжений прежней задачи: 2. Визитов без разметки запуска: 0.

Новая задача учитывается только после подтверждённого запуска. Просмотр прежнего ответа и открытие пустого чата не создают новую задачу.

Сценарии: Первое знакомство, Продолжение.

Повторный визит моделируется с сохранённым контекстом. Между визитами не проходили реальные семь или тридцать дней.

| Группа | Запланировано / есть наблюдения | Зачем её выбрали |
| --- | --- | --- |
| Выбрать быстро | 2 / 2 | Вымышленные покупатели с ограниченным временем: проверяем короткий путь до понятного выбора. |
| Сравнить условия | 2 / 2 | Вымышленные покупатели с фиксированным бюджетом: проверяем итоговую цену и условия билета. |
| Продолжить выбор | 2 / 2 | Вымышленные покупатели, которые выбирают вместе с другим человеком: проверяем сохранение выбора и возврат к нему. |

## Главный вывод

Покажите полную цену и понятный итог выбора.

## Что изменить в следующем релизе

### 1. Показывать полную цену до выбора мест.

**Что увидели:** В списке видна цена билетов, а сбор добавляется только на проверке заказа.

**Кого затронуло:** 3 агентов; 3 сессий со ссылками на действия.

**Что сделать:** Показывать стоимость за нужное число билетов вместе со сбором и фильтровать по итоговой сумме.

**Что проверить:** Доля сценариев, где выбор укладывается в общий бюджет.

Повторить выбор с фиксированным бюджетом. Сумма в списке и перед оплатой должна совпадать.

Основание: [ira-first:e3](#session-1-event-3), [dasha-first:e3](#session-3-event-3), [maksim-first:e3](#session-4-event-3)

### 2. После выбора показывать итог и следующий шаг.

**Что увидели:** После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.

**Кого затронуло:** 2 агентов; 2 сессий со ссылками на действия.

**Что сделать:** Оставлять на экране выбранное событие, места и сумму; показывать «Продолжить» и «Изменить выбор».

**Что проверить:** Доля пользователей, правильно объяснивших результат действия.

После выбора проверить, может ли агент назвать выбранное событие и продолжить без повторного поиска.

Основание: [sasha-first:e2](#session-2-event-2), [oleg-first:e2](#session-6-event-2)

## Кому удалось решить задачу

| Группа | Первая задача: успех / оценено | Новая задача при повторном визите: успех / оценено | Продолжение прежней задачи: успех / оценено | Выбрали бы снова: да / ответили |
| --- | --- | --- | --- | --- |
| Выбрать быстро | 1 / 2 | 0 / 0 | 0 / 0 | 1 / 2 |
| Сравнить условия | 1 / 2 | 0 / 0 | 0 / 0 | 1 / 2 |
| Продолжить выбор | 2 / 2 | 0 / 0 | 2 / 2 | 2 / 2 |

Успех — оценка агента с допустимой ссылкой на наблюдение. Из знаменателя исключены блокировки, технические ошибки, лимиты бюджета и незаконченные запуски. Лимит шагов считается незавершённой задачей. Ноль ответов не означает нулевую удовлетворённость.

## Понятность интерфейса и путь к результату

- Поняли назначение продукта: 6 из 6 ответивших; нет оценки у 0 агентов.
- Поняли следующий шаг: 5 из 6 ответивших; нет оценки у 0 агентов.
- Поняли результат действия: 5 из 6 ответивших; нет оценки у 0 агентов.

| Этап | Достигли / оценили | Без оценки |
| --- | --- | --- |
| Понять, что предлагает продукт | 6 / 6 | 0 |
| Начать задачу | 6 / 6 | 0 |
| Выполнить нужные действия | 6 / 6 | 0 |
| Получить и понять результат | 4 / 6 | 0 |
| Продолжить при повторном визите | 2 / 2 | 4 |

Показаны только этапы, которые агент явно оценил со ссылкой на действие. Для каждого этапа указан собственный знаменатель; это не единая воронка конверсии.

## Удовлетворённость и впечатления

Каждый агент учитывается один раз по последнему допустимому ответу на вопрос. Это оценки AI-агентов после записанных действий, а не удовлетворённость реальных людей.

- Синтетический NPS: 0; n=6.
- CSAT: 4 из 6 поставили четыре или пять; средняя оценка 3.7 из пяти.
- Выбрали бы продукт снова: 4 из 6 ответивших.

NPS = доля оценок девять–десять минус доля оценок ноль–шесть. Оценка рекомендации отделена от удовлетворённости; намерение вернуться отделено от фактического удержания.

### Что понравилось

- Сохранённый выбор помогает продолжить без повторного поиска. · 2 агентов. [lena-resume:e2](#session-7-event-2), [oleg-resume:e2](#session-8-event-2)

## Прогноз продуктовых метрик

Условные расчёты из переданных внешних допущений. Они не предсказывают причинный эффект изменений по отзывам агентов.

Источник: Переданные внешние допущения; источник не описан

Числовой прогноз пока недоступен: нужны внешние данные.

### Какие данные нужны

- Для CAC: monthly\_visitors, marketing\_spend и paid\_conversion \[low, high\] из внешних данных.
- Для MAU: внешний диапазон mau \[low, high\] с определением активного пользователя.
- Для среднего DAU: mau и active\_days \[low, high\] на пользователя за 30 дней.
- Для возвращений: return\_rate \[low, high\] из аналитики с окном наблюдения и когортой.

## План проверки изменений

Сначала повторите выбранные задачи с тем же составом групп и моделями. Сравните долю успешных задач, понятность интерфейса и причины остановки. Затем проверьте эффект на реальных пользователях.

## Расходы на исследование

| Статья | USD |
| --- | --- |
| Подтверждено провайдером | $0.0000 |
| Оценка по резерву | $0.0000 |
| Неопределённая стоимость · учтённая сумма | $0.0000 |
| Резерв активных запросов | $0.0000 |
| Всего учтено в ограничении бюджета | $0.0000 |
| Лимит бюджета | $0.0000 |
| Остаток по учёту бюджета | $0.0000 |

Учтённая сумма включает подтверждённые расходы, оценки и удерживаемые резервы; она не является фактическим счётом провайдера.

Записей расходов пока нет.

## Статусы и модели

| Текущий статус | Сессии |
| --- | --- |
| Завершены | 8 |

| Модель | Успешно / оценено | Ошибки / всего | Блокировки / всего |
| --- | --- | --- | --- |
| fixture/scripted-persona | 6 / 8 | 0 / 8 | 0 / 8 |

Сравнение моделей описательное: состав групп и задачи могут различаться. Несколько агентов одной модели не являются независимой выборкой людей.

Ограничения запуска:

- DEMO: authored fixture, no live product or model calls.

## Записи сессий

Полные исходные записи также сохранены в report.json. Текст ниже передан без содержательных дополнений.

<a id="session-1"></a>

### Сессия ira-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 8,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Выбор сделан быстро, но полная сумма появилась только после выбора мест.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;ira-first:e3&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 4,
    &quot;effort&quot;: 2,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;ira-first:e3&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сделан быстро, но полная сумма появилась только после выбора мест.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;ira-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сделан быстро, но полная сумма появилась только после выбора мест.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;ira-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сделан быстро, но полная сумма появилась только после выбора мест.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;ira-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сделан быстро, но полная сумма появилась только после выбора мест.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;ira-first:e3&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[
    &quot;События удобно сравнивать в одном месте.&quot;
  \],
  &quot;dislikes&quot;: \[
    &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;
  \],
  &quot;recommendations&quot;: \[
    \{
      &quot;issue\_key&quot;: &quot;upfront\_total&quot;,
      &quot;scope&quot;: &quot;product&quot;,
      &quot;stage&quot;: &quot;action&quot;,
      &quot;change&quot;: &quot;Показывать полную цену до выбора мест.&quot;,
      &quot;reason&quot;: &quot;Поздний сбор заставляет перепроверять бюджет или начинать выбор заново.&quot;,
      &quot;observed&quot;: &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;,
      &quot;proposed&quot;: &quot;Показывать стоимость за нужное число билетов вместе со сбором и фильтровать по итоговой сумме.&quot;,
      &quot;expected\_metric&quot;: &quot;Доля сценариев, где выбор укладывается в общий бюджет.&quot;,
      &quot;how\_to\_verify&quot;: &quot;Повторить выбор с фиксированным бюджетом. Сумма в списке и перед оплатой должна совпадать.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;ira-first:e3&quot;
      \]
    \}
  \]
\}

<a id="session-1-event-1"></a>

#### Событие ira-first:e1

\{
  &quot;id&quot;: &quot;ira-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/ira&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Найди два билета на небольшой джазовый концерт в субботу после 19:00. Хочу быстро выбрать, до 6 000 ₽ за двоих.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 390,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-1-event-2"></a>

#### Событие ira-first:e2

\{
  &quot;id&quot;: &quot;ira-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;choose-seats&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/ira&quot;,
    &quot;title&quot;: &quot;Места на концерт&quot;,
    &quot;text&quot;: &quot;Вечер джаза\\nДва билета — 4 400 ₽\\nВыбрать места&quot;,
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;choose-seats&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Выбрать места&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-1-event-3"></a>

#### Событие ira-first:e3

\{
  &quot;id&quot;: &quot;ira-first:e3&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/ira&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;Подходит «Вечер джаза», суббота, 19:30. Небольшой зал, 120 мест.\\nДва соседних места: ряд 5, места 7 и 8. Цена билетов — 4 400 ₽. На следующем шаге сервисный сбор — 400 ₽. Итого — 4 800 ₽.\\nВыбраны: два билета, ряд 5, места 7 и 8. Следующий шаг — проверить заказ. Оплата ещё не выполнена.&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-2"></a>

### Сессия sasha-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;partial&quot;,
  &quot;rating&quot;: 5,
  &quot;return\_intent&quot;: false,
  &quot;summary&quot;: &quot;После выбора мест непонятно, сохранились ли они и как продолжить.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;sasha-first:e2&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 2,
    &quot;effort&quot;: 4,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: false,
    &quot;result\_clear&quot;: false,
    &quot;evidence\_ids&quot;: \[
      &quot;sasha-first:e2&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;После выбора мест непонятно, сохранились ли они и как продолжить.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;sasha-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;После выбора мест непонятно, сохранились ли они и как продолжить.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;sasha-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;После выбора мест непонятно, сохранились ли они и как продолжить.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;sasha-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: false,
      &quot;note&quot;: &quot;После выбора мест непонятно, сохранились ли они и как продолжить.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;sasha-first:e2&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[\],
  &quot;dislikes&quot;: \[
    &quot;После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.&quot;
  \],
  &quot;recommendations&quot;: \[
    \{
      &quot;issue\_key&quot;: &quot;selection\_confirmation&quot;,
      &quot;scope&quot;: &quot;product&quot;,
      &quot;stage&quot;: &quot;result&quot;,
      &quot;change&quot;: &quot;После выбора показывать итог и следующий шаг.&quot;,
      &quot;reason&quot;: &quot;Без итога пользователь не понимает, сохранился ли результат и где его продолжить.&quot;,
      &quot;observed&quot;: &quot;После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.&quot;,
      &quot;proposed&quot;: &quot;Оставлять на экране выбранное событие, места и сумму; показывать «Продолжить» и «Изменить выбор».&quot;,
      &quot;expected\_metric&quot;: &quot;Доля пользователей, правильно объяснивших результат действия.&quot;,
      &quot;how\_to\_verify&quot;: &quot;После выбора проверить, может ли агент назвать выбранное событие и продолжить без повторного поиска.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;sasha-first:e2&quot;
      \]
    \}
  \]
\}

<a id="session-2-event-1"></a>

#### Событие sasha-first:e1

\{
  &quot;id&quot;: &quot;sasha-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/sasha&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Хочу два соседних места на концерт «Вечер джаза». Выбери ряд поближе к сцене и покажи, что выбрано. Пока без оплаты.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 1360,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-2-event-2"></a>

#### Событие sasha-first:e2

\{
  &quot;id&quot;: &quot;sasha-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/sasha&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;Готово.\\nСобытия\\nВечер джаза · суббота · 19:30\\nФортепианный вечер · суббота · 20:00\\nНайти событие&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-3"></a>

### Сессия dasha-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;partial&quot;,
  &quot;rating&quot;: 6,
  &quot;return\_intent&quot;: false,
  &quot;summary&quot;: &quot;Сервисный сбор появился поздно; итог превысил заданный бюджет.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;dasha-first:e3&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 2,
    &quot;effort&quot;: 4,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;dasha-first:e3&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Сервисный сбор появился поздно; итог превысил заданный бюджет.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;dasha-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Сервисный сбор появился поздно; итог превысил заданный бюджет.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;dasha-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Сервисный сбор появился поздно; итог превысил заданный бюджет.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;dasha-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: false,
      &quot;note&quot;: &quot;Сервисный сбор появился поздно; итог превысил заданный бюджет.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;dasha-first:e3&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[\],
  &quot;dislikes&quot;: \[
    &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;
  \],
  &quot;recommendations&quot;: \[
    \{
      &quot;issue\_key&quot;: &quot;upfront\_total&quot;,
      &quot;scope&quot;: &quot;product&quot;,
      &quot;stage&quot;: &quot;action&quot;,
      &quot;change&quot;: &quot;Показывать полную цену до выбора мест.&quot;,
      &quot;reason&quot;: &quot;Поздний сбор заставляет перепроверять бюджет или начинать выбор заново.&quot;,
      &quot;observed&quot;: &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;,
      &quot;proposed&quot;: &quot;Показывать стоимость за нужное число билетов вместе со сбором и фильтровать по итоговой сумме.&quot;,
      &quot;expected\_metric&quot;: &quot;Доля сценариев, где выбор укладывается в общий бюджет.&quot;,
      &quot;how\_to\_verify&quot;: &quot;Повторить выбор с фиксированным бюджетом. Сумма в списке и перед оплатой должна совпадать.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;dasha-first:e3&quot;
      \]
    \}
  \]
\}

<a id="session-3-event-1"></a>

#### Событие dasha-first:e1

\{
  &quot;id&quot;: &quot;dasha-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/dasha&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Подбери два билета на концерт в субботу. Общий бюджет — 5 000 ₽, включая все сборы. Покажи итоговую цену сразу.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 390,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-3-event-2"></a>

#### Событие dasha-first:e2

\{
  &quot;id&quot;: &quot;dasha-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;choose-seats&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/dasha&quot;,
    &quot;title&quot;: &quot;Места на концерт&quot;,
    &quot;text&quot;: &quot;Вечер джаза\\nДва билета — 4 800 ₽\\nВыбрать места&quot;,
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;choose-seats&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Выбрать места&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-3-event-3"></a>

#### Событие dasha-first:e3

\{
  &quot;id&quot;: &quot;dasha-first:e3&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/dasha&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;«Вечер джаза», суббота, 19:30. Два билета по 2 400 ₽ — 4 800 ₽.\\nНа шаге проверки заказа добавлен сервисный сбор 480 ₽. Итого — 5 280 ₽. Это больше указанного общего бюджета.\\nВыбор можно изменить, вернувшись к списку мест.&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-4"></a>

### Сессия maksim-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 8,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;maksim-first:e3&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 4,
    &quot;effort&quot;: 2,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;maksim-first:e3&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;maksim-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;maksim-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;maksim-first:e3&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Варианты удалось сравнить, но итоговая цена потребовала дополнительного шага.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;maksim-first:e3&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[
    &quot;События удобно сравнивать в одном месте.&quot;
  \],
  &quot;dislikes&quot;: \[
    &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;
  \],
  &quot;recommendations&quot;: \[
    \{
      &quot;issue\_key&quot;: &quot;upfront\_total&quot;,
      &quot;scope&quot;: &quot;product&quot;,
      &quot;stage&quot;: &quot;action&quot;,
      &quot;change&quot;: &quot;Показывать полную цену до выбора мест.&quot;,
      &quot;reason&quot;: &quot;Поздний сбор заставляет перепроверять бюджет или начинать выбор заново.&quot;,
      &quot;observed&quot;: &quot;В списке видна цена билетов, а сбор добавляется только на проверке заказа.&quot;,
      &quot;proposed&quot;: &quot;Показывать стоимость за нужное число билетов вместе со сбором и фильтровать по итоговой сумме.&quot;,
      &quot;expected\_metric&quot;: &quot;Доля сценариев, где выбор укладывается в общий бюджет.&quot;,
      &quot;how\_to\_verify&quot;: &quot;Повторить выбор с фиксированным бюджетом. Сумма в списке и перед оплатой должна совпадать.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;maksim-first:e3&quot;
      \]
    \}
  \]
\}

<a id="session-4-event-1"></a>

#### Событие maksim-first:e1

\{
  &quot;id&quot;: &quot;maksim-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/maksim&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Сравни два варианта мест на «Вечер джаза». Мне важны итоговая цена за двоих и условия возврата, до оплаты.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 1360,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-4-event-2"></a>

#### Событие maksim-first:e2

\{
  &quot;id&quot;: &quot;maksim-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;choose-seats&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/maksim&quot;,
    &quot;title&quot;: &quot;Места на концерт&quot;,
    &quot;text&quot;: &quot;Вечер джаза\\nДва билета — 4 400 ₽\\nВыбрать места&quot;,
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;choose-seats&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Выбрать места&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-4-event-3"></a>

#### Событие maksim-first:e3

\{
  &quot;id&quot;: &quot;maksim-first:e3&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/maksim&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;Вариант А: ряд 5 — 4 400 ₽ за два билета, сбор 400 ₽, итого 4 800 ₽.\\nВариант Б: ряд 3 — 5 200 ₽ за два билета, сбор 400 ₽, итого 5 600 ₽.\\nПолная сумма отображается на проверке заказа; в списке указана только цена билетов. Оба варианта допускают возврат по условиям организатора, которые открываются отдельной ссылкой.\\nВыбран вариант А. Следующий шаг — проверить заказ; оплата не выполнялась.&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-5"></a>

### Сессия lena-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 9,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Выбор сохранён; понятны итоговая сумма и способ вернуться.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;lena-first:e2&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 5,
    &quot;effort&quot;: 2,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;lena-first:e2&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сохранён; понятны итоговая сумма и способ вернуться.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;lena-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сохранён; понятны итоговая сумма и способ вернуться.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;lena-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сохранён; понятны итоговая сумма и способ вернуться.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;lena-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор сохранён; понятны итоговая сумма и способ вернуться.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;lena-first:e2&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[
    &quot;События удобно сравнивать в одном месте.&quot;
  \],
  &quot;dislikes&quot;: \[\],
  &quot;recommendations&quot;: \[\]
\}

<a id="session-5-event-1"></a>

#### Событие lena-first:e1

\{
  &quot;id&quot;: &quot;lena-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/lena&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Подбери два места на джазовый концерт и сохрани выбор, чтобы я могла обсудить его и вернуться позже.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 390,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-5-event-2"></a>

#### Событие lena-first:e2

\{
  &quot;id&quot;: &quot;lena-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/lena&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;Выбор сохранён: «Вечер джаза», суббота, 19:30, ряд 5, места 9 и 10.\\nДва билета — 4 400 ₽, сервисный сбор — 400 ₽. Итого — 4 800 ₽.\\nВернуться к выбору можно в разделе «Сохранённое». Оплата не выполнена; наличие мест может измениться.&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-6"></a>

### Сессия oleg-first

Модель: fixture/scripted-persona · Режим: Первое знакомство · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 9,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Подборка сохранена, но короткое «Готово» не объясняет, где она находится.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;oleg-first:e2&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 4,
    &quot;effort&quot;: 2,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: false,
    &quot;evidence\_ids&quot;: \[
      &quot;oleg-first:e2&quot;
    \]
  \},
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;entry&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Подборка сохранена, но короткое «Готово» не объясняет, где она находится.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;start&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Подборка сохранена, но короткое «Готово» не объясняет, где она находится.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;action&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Подборка сохранена, но короткое «Готово» не объясняет, где она находится.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-first:e2&quot;
      \]
    \},
    \{
      &quot;stage&quot;: &quot;result&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Подборка сохранена, но короткое «Готово» не объясняет, где она находится.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-first:e2&quot;
      \]
    \}
  \],
  &quot;likes&quot;: \[
    &quot;События удобно сравнивать в одном месте.&quot;
  \],
  &quot;dislikes&quot;: \[
    &quot;После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.&quot;
  \],
  &quot;recommendations&quot;: \[
    \{
      &quot;issue\_key&quot;: &quot;selection\_confirmation&quot;,
      &quot;scope&quot;: &quot;product&quot;,
      &quot;stage&quot;: &quot;result&quot;,
      &quot;change&quot;: &quot;После выбора показывать итог и следующий шаг.&quot;,
      &quot;reason&quot;: &quot;Без итога пользователь не понимает, сохранился ли результат и где его продолжить.&quot;,
      &quot;observed&quot;: &quot;После действия нет заметной карточки сохранённого выбора; приходится искать продолжение.&quot;,
      &quot;proposed&quot;: &quot;Оставлять на экране выбранное событие, места и сумму; показывать «Продолжить» и «Изменить выбор».&quot;,
      &quot;expected\_metric&quot;: &quot;Доля пользователей, правильно объяснивших результат действия.&quot;,
      &quot;how\_to\_verify&quot;: &quot;После выбора проверить, может ли агент назвать выбранное событие и продолжить без повторного поиска.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-first:e2&quot;
      \]
    \}
  \]
\}

<a id="session-6-event-1"></a>

#### Событие oleg-first:e1

\{
  &quot;id&quot;: &quot;oleg-first:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;send&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/oleg&quot;,
    &quot;title&quot;: &quot;Seatly · демонстрационный продукт&quot;,
    &quot;text&quot;: &quot;Сравни камерный джаз и фортепианный концерт в субботу. Сохрани оба варианта, решение приму позже.&quot;,
    &quot;task\_state&quot;: &quot;running&quot;,
    &quot;viewport&quot;: \{
      &quot;width&quot;: 1360,
      &quot;height&quot;: 900
    \},
    &quot;elements&quot;: \[
      \{
        &quot;id&quot;: &quot;send&quot;,
        &quot;role&quot;: &quot;button&quot;,
        &quot;name&quot;: &quot;Отправить&quot;
      \}
    \]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_started&quot;: true
  \}
\}

<a id="session-6-event-2"></a>

#### Событие oleg-first:e2

\{
  &quot;id&quot;: &quot;oleg-first:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/oleg&quot;,
    &quot;title&quot;: &quot;Результат выбора&quot;,
    &quot;text&quot;: &quot;Подборка сохранена.\\nСобытия\\nВечер джаза · от 2 200 ₽\\nФортепианный вечер · от 1 800 ₽\\nСохранённое&quot;,
    &quot;task\_state&quot;: &quot;completed&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;,
    &quot;task\_completed&quot;: true
  \}
\}

<a id="session-7"></a>

### Сессия lena-resume

Модель: fixture/scripted-persona · Режим: Продолжение · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 9,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Сохранённый выбор найден; повторный поиск не понадобился.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;lena-resume:e2&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 5,
    &quot;effort&quot;: 1,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;lena-resume:e2&quot;
    \]
  \},
  &quot;likes&quot;: \[
    &quot;Сохранённый выбор помогает продолжить без повторного поиска.&quot;
  \],
  &quot;dislikes&quot;: \[\],
  &quot;recommendations&quot;: \[\],
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;return&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор восстановлен.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;lena-resume:e2&quot;
      \]
    \}
  \]
\}

<a id="session-7-event-1"></a>

#### Событие lena-resume:e1

\{
  &quot;id&quot;: &quot;lena-resume:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;saved&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/lena&quot;,
    &quot;text&quot;: &quot;Продолжим сохранённый выбор. Покажи, что было выбрано, и как перейти к проверке заказа. Пока без оплаты.&quot;,
    &quot;title&quot;: &quot;Сохранённое&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-7-event-2"></a>

#### Событие lena-resume:e2

\{
  &quot;id&quot;: &quot;lena-resume:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/lena&quot;,
    &quot;text&quot;: &quot;Сохранённый выбор открыт: «Вечер джаза», суббота, 19:30. Ряд 5, места 9 и 10. Итого — 4 800 ₽ со сбором. Следующий шаг — «Проверить заказ». Оплата не выполнялась.&quot;,
    &quot;title&quot;: &quot;Продолжение выбора&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-8"></a>

### Сессия oleg-resume

Модель: fixture/scripted-persona · Режим: Продолжение · Статус: Завершены

**Отзыв:**

\{
  &quot;outcome&quot;: &quot;success&quot;,
  &quot;rating&quot;: 9,
  &quot;return\_intent&quot;: true,
  &quot;summary&quot;: &quot;Сохранённый выбор найден; повторный поиск не понадобился.&quot;,
  &quot;evidence\_ids&quot;: \[
    &quot;oleg-resume:e2&quot;
  \],
  &quot;assessment&quot;: \{
    &quot;satisfaction&quot;: 5,
    &quot;effort&quot;: 1,
    &quot;purpose\_clear&quot;: true,
    &quot;next\_step\_clear&quot;: true,
    &quot;result\_clear&quot;: true,
    &quot;evidence\_ids&quot;: \[
      &quot;oleg-resume:e2&quot;
    \]
  \},
  &quot;likes&quot;: \[
    &quot;Сохранённый выбор помогает продолжить без повторного поиска.&quot;
  \],
  &quot;dislikes&quot;: \[\],
  &quot;recommendations&quot;: \[\],
  &quot;journey&quot;: \[
    \{
      &quot;stage&quot;: &quot;return&quot;,
      &quot;reached&quot;: true,
      &quot;note&quot;: &quot;Выбор восстановлен.&quot;,
      &quot;evidence\_ids&quot;: \[
        &quot;oleg-resume:e2&quot;
      \]
    \}
  \]
\}

<a id="session-8-event-1"></a>

#### Событие oleg-resume:e1

\{
  &quot;id&quot;: &quot;oleg-resume:e1&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;click&quot;,
    &quot;target&quot;: &quot;saved&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/oleg&quot;,
    &quot;text&quot;: &quot;Продолжим сохранённый выбор. Покажи, что было выбрано, и как перейти к проверке заказа. Пока без оплаты.&quot;,
    &quot;title&quot;: &quot;Сохранённое&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}

<a id="session-8-event-2"></a>

#### Событие oleg-resume:e2

\{
  &quot;id&quot;: &quot;oleg-resume:e2&quot;,
  &quot;action&quot;: \{
    &quot;type&quot;: &quot;observe&quot;
  \},
  &quot;observation&quot;: \{
    &quot;url&quot;: &quot;https://seatly.example/chat/oleg&quot;,
    &quot;text&quot;: &quot;Сохранённый выбор открыт: «Вечер джаза», суббота, 19:30. В подборке также остался «Фортепианный вечер». Можно выбрать места на любом из событий. Следующий шаг — «Проверить заказ». Оплата не выполнялась.&quot;,
    &quot;title&quot;: &quot;Продолжение выбора&quot;,
    &quot;elements&quot;: \[\]
  \},
  &quot;result&quot;: \{
    &quot;status&quot;: &quot;ok&quot;
  \}
\}
