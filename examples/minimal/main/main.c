#include <stdio.h>
#include <stdlib.h>
#include "cJSON.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "nvs_flash.h"
void app_main(void) {
    cJSON *value = cJSON_Parse("{\"answer\":42}");
    int answer = cJSON_GetObjectItem(value, "answer")->valueint;
    printf("answer=%d\n", answer);
    cJSON_Delete(value);
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    wifi_init_config_t configuration = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&configuration));
    ESP_ERROR_CHECK(esp_wifi_deinit());
    return;
}
