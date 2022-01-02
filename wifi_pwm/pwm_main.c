#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <aos/kernel.h>
#include <aos/pwm.h>
#include "ulog/ulog.h"
#include "cJSON.h"
#include "sys/socket.h"
#include "string.h"

// 定义参数名
#define ULOG_MOD "pwm_main"
// ns 0.5ms 0°
#define SERVO_0 (0.5 * 1000 * 1000)
// ns 2.5ms 180°
#define SERVO_180 (2.5 * 1000 * 1000)
// tcp buffer
#define BUFFER_MAX_SIZE 1024
// 周期 4000000ns 4ms
int period = 4 * 1000 * 1000;
int duty = SERVO_0;

int pwm_main(int argc, char *argv[])
{

    aos_status_t ret;
    aos_pwm_ref_t ref;
    aos_pwm_attr_t attr;
    // PWM 通道
    int channel = 0;
    // socket clientfd
    int clientfd;
    // socket client
    struct sockaddr_in addr;
    // 端口
    int port = 233;
    // ip
    // char *ipaddr = "192.168.31.235";
    //char *ipaddr = "192.168.31.196";
    char *ipaddr = "192.168.137.194";
    // 超时
    struct timeval timeout;
    // tcp buff
    char *pbuf = NULL;
    // 读取的长度
    int readlen = 0;
    // 上报信息
    char report[100] = {0};
    // 开门
    char *open_door = "open";
    // 关门
    char *close_door = "close";
    // 开关门状态
    bool isOpen = false;
    // 获取设备引用
    ret = aos_pwm_get(&ref, channel);
    if (ret)
    {
        LOGE(ULOG_MOD, "aos_pwm_set_attr fail, ret %d\r\n", ret);
        return -1;
    }
    // pwm属性设置
    // 周期
    attr.period = period;
    // 占空比
    attr.duty_cycle = duty;
    // 极性
    attr.polarity = AOS_PWM_POLARITY_NORMAL;
    // 使能
    attr.enabled = true;
    ret = aos_pwm_set_attr(&ref, &attr);
    if (ret)
    {
        LOGE(ULOG_MOD, "aos_pwm_set_attr fail, ret %d\r\n", ret);
        goto out;
    }
    LOGI(ULOG_MOD, "pwm set success\r\n");
    memset(&addr, 0, sizeof(addr));
    // 设置端口
    addr.sin_port = htons(port);
    if (0 == addr.sin_port)
    {
        LOGE(ULOG_MOD, "invalid input port info %d \r\n", port);
        goto out;
    }
    //设置ip
    addr.sin_addr.s_addr = inet_addr(ipaddr);
    if (IPADDR_NONE == addr.sin_addr.s_addr)
    {
        LOGE(ULOG_MOD, "invalid input addr info %s \r\n", ipaddr);
        goto out;
    }
    //
    addr.sin_family = AF_INET;
    // socket字获取
    clientfd = socket(AF_INET, SOCK_STREAM, 0);
    if (clientfd < 0)
    {
        LOGE(ULOG_MOD, "fail to create socket errno = %d\r\n", errno);
        goto out;
    }
    LOGI(ULOG_MOD, "client fd=%d, ip=%s, port=%d\r\n", clientfd, ipaddr, addr.sin_port);
    timeout.tv_sec = 15;
    timeout.tv_usec = 0;
    // 可选设置
    if (setsockopt(clientfd, SOL_SOCKET, SO_RCVTIMEO, (char *)&timeout, sizeof(timeout)) < 0)
    {
        LOGE(ULOG_MOD, "setsockopt failed, errno: %d\r\n", errno);
        goto err;
    }
    // 连接
    if (connect(clientfd, (struct sockaddr *)&addr, sizeof(addr)) != 0)
    {
        LOGE(ULOG_MOD, "Connect failed, errno = %d, ip %s port %d \r\n", errno, ipaddr, port);
        goto err;
    }
    // buffer 申请
    pbuf = aos_malloc(BUFFER_MAX_SIZE);
    if (NULL == pbuf)
    {
        LOGE(ULOG_MOD, "fail to malloc memory %d at %s %d \r\n", BUFFER_MAX_SIZE, __FUNCTION__, __LINE__);
        goto err;
    }
    while (1)
    {
        isOpen = SERVO_180 == attr.duty_cycle ? true : false;
        snprintf(report, 100, "{\"period\":%d,\"duty\":%d,\"isOpen\":%d}", attr.period, attr.duty_cycle, isOpen);
        LOGI(ULOG_MOD, "send data:\"%s\"\r\n", report);
        if ((ret = send(clientfd, report, strlen(report), 0)) <= 0)
        {
            LOGE(ULOG_MOD, "send data failed, errno = %d.\r\n", errno);
            goto err;
        }
        memset(pbuf, 0, BUFFER_MAX_SIZE);
        LOGI(ULOG_MOD, "read data from server...\r\n");
        readlen = recv(clientfd, pbuf, BUFFER_MAX_SIZE - 1, 0);
        if (readlen < 0)
        {
            LOGE(ULOG_MOD, "recv failed, errno = %d.\r\n", errno);
            goto err;
        }

        if (readlen == 0)
        {
            LOGD(ULOG_MOD, "recv buf len is %d \r\n", readlen);
            continue;
        }

        // LOGI(ULOG_MOD, "recv server reply len %d. str: %s\r\n", readlen, pbuf);
        if (0 == strcmp(pbuf, open_door))
        {
            // 开门
            attr.duty_cycle = SERVO_180;
            ret = aos_pwm_set_attr(&ref, &attr);
            if (ret)
            {
                LOGE(ULOG_MOD, "aos_pwm_set_attr fail, ret %d\r\n", ret);
                goto out;
            }
            LOGI(ULOG_MOD, "set servo to 180");
        }
        else if (0 == strcmp(pbuf, close_door))
        {
            //关门
            attr.duty_cycle = SERVO_0;
            ret = aos_pwm_set_attr(&ref, &attr);
            if (ret)
            {
                LOGE(ULOG_MOD, "aos_pwm_set_attr fail, ret %d\r\n", ret);
                goto out;
            }
            LOGI(ULOG_MOD, "set servo to 0");
        }
        aos_msleep(100);
    }
    close(clientfd);
    aos_free(pbuf);
    aos_pwm_put(&ref);
    return 0;
err:
    close(clientfd);
    if (NULL != pbuf)
    {
        aos_free(pbuf);
    }
out:
    aos_pwm_put(&ref);
    return -1;
}