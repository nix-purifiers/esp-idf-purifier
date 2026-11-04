#include <stdio.h>
#include <stdlib.h>
#include "cJSON.h"
void app_main(void) {
    cJSON *value = cJSON_Parse("{\"answer\":42}");
    int answer = cJSON_GetObjectItem(value, "answer")->valueint;
    printf("answer=%d\n", answer);
    cJSON_Delete(value);
    exit(answer == 42 ? 0 : 1);
}
