<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes"/>
    <xsl:template match="/">
        <html>
            <head>
                <title>LNST results</title>
                <meta charset="utf-8"/>
                <link rel="stylesheet" type="text/css" href="http://www.lnst-project.org/files/result_xslt/xml_to_html.css"/>
                <script type="text/javascript" src="http://www.lnst-project.org/files/result_xslt/xml_to_html.js"></script>
            </head>
            <body>
                <h2>LNST results</h2>
                <xsl:apply-templates select="results/recipe"/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="recipe">
        <h3><xsl:value-of select="@name"/> match <xsl:value-of select="@match_num"/></h3>
        <xsl:apply-templates select="pool_match"/>
        <table class="lnst_results">
            <tr><th colspan="5">Task</th></tr>
            <tr><th>Host</th><th>Bg ID</th><th>Command</th><th>Result</th><th>Result message</th></tr>
            <xsl:apply-templates select="task"/>
        </table>
    </xsl:template>

    <xsl:template match="pool_match">
        <table class="match_description">
            <tr><th colspan="3">Match description</th></tr>
            <xsl:if test="@virtual = 'true'">
                <tr><td colspan="3">Match is virtual</td></tr>
            </xsl:if>
            <tr><th>machine id</th><th>pool id</th><th>interface match description</th></tr>
            <xsl:apply-templates select="m_match"/>
        </table>
    </xsl:template>

    <xsl:template match="m_match">
        <tr>
            <td>
                <xsl:value-of select="@host_id"/>
            </td>
            <td>
                <xsl:value-of select="@pool_id"/>
            </td>
            <xsl:choose>
                <xsl:when test="if_match">
                    <td>
                        <table class="if_match_description">
                            <tr><th>interface id</th><th>pool interface id</th></tr>
                            <xsl:apply-templates select="if_match"/>
                        </table>
                    </td>
                </xsl:when>
                <xsl:otherwise>
                    <td>
                        no interface match
                    </td>
                </xsl:otherwise>
            </xsl:choose>
        </tr>
    </xsl:template>

    <xsl:template match="if_match">
        <tr>
            <td>
                <xsl:value-of select="@if_id"/>
            </td>
            <td>
                <xsl:value-of select="@pool_if_id"/>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="task">
        <tr class="task_header"><th colspan="5">Task <xsl:value-of select="position()"/></th></tr>
        <xsl:apply-templates select="command">
            <xsl:with-param name="task_id" select="position()"/>
        </xsl:apply-templates>
    </xsl:template>

    <xsl:template match="command">
        <xsl:param name="task_id"/>
        <tr class="tr_top">
            <xsl:attribute name="name">task_id=<xsl:value-of select="$task_id"/>host_id=<xsl:value-of select="@host"/>bg_id=<xsl:value-of select="@proc_id"/></xsl:attribute>
            <xsl:choose>
                <xsl:when test="@type='exec'">
                    <xsl:call-template name="cmd_exec"/>
                </xsl:when>
                <xsl:when test="@type='ctl_wait'">
                    <xsl:call-template name="cmd_ctl_wait"/>
                </xsl:when>
                <xsl:when test="@type='test'">
                    <xsl:call-template name="cmd_test"/>
                </xsl:when>
                <xsl:when test="@type='config'">
                    <xsl:call-template name="cmd_config"/>
                </xsl:when>
                <xsl:when test="@type='intr'">
                    <xsl:call-template name="cmd_intr"/>
                </xsl:when>
                <xsl:when test="@type='wait'">
                    <xsl:call-template name="cmd_wait"/>
                </xsl:when>
                <xsl:when test="@type='kill'">
                    <xsl:call-template name="cmd_kill"/>
                </xsl:when>
                <xsl:otherwise>
                    <td>
                        unknown command type
                    </td>
                </xsl:otherwise>
            </xsl:choose>

            <xsl:apply-templates select="result"/>
        </tr>

        <xsl:call-template name="res_data">
            <xsl:with-param name="task_id" select="$task_id"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template name="cmd_exec">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
            <xsl:if test="@bg_id">
                <xsl:value-of select="@bg_id"/>
            </xsl:if>
        </td>
        <td>
            <xsl:value-of select="@command"/>
        </td>
    </xsl:template>

    <xsl:template name="cmd_ctl_wait">
        <td>
            Controller
        </td>
        <td>
        </td>
        <td>
            wait <xsl:value-of select="@seconds"/>s
        </td>
    </xsl:template>

    <xsl:template name="cmd_test">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
            <xsl:if test="@bg_id">
                <xsl:value-of select="@bg_id"/>
            </xsl:if>
        </td>
        <td>
            <xsl:value-of select="@module"/>
        </td>
    </xsl:template>

    <xsl:template name="cmd_config">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
        </td>
        <td>
            config
        </td>
    </xsl:template>

    <xsl:template name="cmd_intr">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
            <xsl:if test="@proc_id">
                <xsl:value-of select="@proc_id"/>
            </xsl:if>
        </td>
        <td>
            interrupt
        </td>
    </xsl:template>

    <xsl:template name="cmd_kill">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
            <xsl:if test="@proc_id">
                <xsl:value-of select="@proc_id"/>
            </xsl:if>
        </td>
        <td>
            kill
        </td>
    </xsl:template>

    <xsl:template name="cmd_wait">
        <td>
            <xsl:value-of select="@host"/>
        </td>
        <td>
            <xsl:if test="@proc_id">
                <xsl:value-of select="@proc_id"/>
            </xsl:if>
        </td>
        <td>
            wait
        </td>
    </xsl:template>

    <xsl:template match="result">
        <xsl:choose>
            <xsl:when test="@result='PASS'">
                <td class="result_pass">PASSED</td>
            </xsl:when>
            <xsl:otherwise>
                <td class="result_fail">FAILED</td>
            </xsl:otherwise>
        </xsl:choose>
        <td>
            <xsl:if test="message">
                <xsl:value-of select="message"/>
            </xsl:if>
        </td>
    </xsl:template>

    <xsl:template match="result_data">
        <table class="result_data">
            <tr><th>Result Data:</th></tr>
            <xsl:for-each select="*">
                <xsl:call-template name="res_data_dict_item"/>
            </xsl:for-each>
        </table>
    </xsl:template>

    <xsl:template name="res_data_dict_item">
        <tr>
            <td>
                <xsl:value-of select="local-name()"/>
            </td>
            <td>
                <xsl:choose>
                    <xsl:when test="@type = 'list'">
                        <ul>
                            <xsl:for-each select="*">
                                <li>
                                    <xsl:call-template name="res_data_list_item"/>
                                </li>
                            </xsl:for-each>
                        </ul>
                    </xsl:when>
                    <xsl:when test="@type = 'dict'">
                        <table class="result_data">
                            <xsl:for-each select="*">
                                <xsl:call-template name="res_data_dict_item"/>
                            </xsl:for-each>
                        </table>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="text()"/>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template name="res_data_list_item">
        <xsl:choose>
            <xsl:when test="@type = 'list'">
                <ul>
                    <xsl:for-each select="*">
                        <li>
                            <xsl:call-template name="res_data_list_item"/>
                        </li>
                    </xsl:for-each>
                </ul>
            </xsl:when>
            <xsl:when test="@type = 'dict'">
                <table class="result_data">
                    <xsl:for-each select="*">
                        <xsl:call-template name="res_data_dict_item"/>
                    </xsl:for-each>
                </table>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="text()"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template name="result_button">
        <xsl:param name="task_id"/>
        <button type="button">
            <xsl:choose>
                <xsl:when test="@bg_id">
                    <xsl:attribute name="onclick">
                        toggleResultData(event, '<xsl:value-of select="$task_id"/>', '<xsl:value-of select="@host"/>', '<xsl:value-of select="@bg_id"/>');
                    </xsl:attribute>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:attribute name="onclick">
                        toggleResultData(event);
                    </xsl:attribute>
                </xsl:otherwise>
            </xsl:choose>
            Show result data
        </button>
    </xsl:template>

    <xsl:template name="highlight_button">
        <xsl:param name="task_id"/>
        <button type="button">
            <xsl:attribute name="onclick">
                highlightResultData(event, '<xsl:value-of select="$task_id"/>', '<xsl:value-of select="@host"/>', '<xsl:value-of select="@bg_id"/>');
            </xsl:attribute>
            Highlight result command
        </button>
    </xsl:template>

    <xsl:template name="res_data">
        <xsl:param name="task_id"/>
        <xsl:choose>
            <xsl:when test="result_data">
                <tr class="tr_bottom">
                    <td class="button">
                        <xsl:call-template name="result_button">
                            <xsl:with-param name="task_id" select="$task_id"/>
                        </xsl:call-template>
                    </td>
                    <td>
                    </td>
                    <td colspan="3" style="display:none;">
                        <xsl:apply-templates select="result_data"/>
                    </td>
                </tr>
            </xsl:when>
            <xsl:when test="@bg_id">
                <tr class="tr_bottom">
                    <td class="button">
                        <xsl:call-template name="highlight_button">
                            <xsl:with-param name="task_id" select="$task_id"/>
                        </xsl:call-template>
                    </td>
                    <td>
                    </td>
                    <td colspan="3">
                        <div class="no_result_data">
                            Result data for background commands located in the corresponding wait/intr/kill command.
                        </div>
                    </td>
                </tr>
            </xsl:when>
            <xsl:otherwise>
                <tr class="tr_bottom">
                    <xsl:attribute name="name">task_id=<xsl:value-of select="$task_id"/>host_id=<xsl:value-of select="@host"/>bg_id=<xsl:value-of select="@proc_id"/></xsl:attribute>
                    <td>
                    </td>
                    <td>
                    </td>
                    <td colspan="3">
                        <div class="no_result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </td>
                </tr>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
</xsl:stylesheet>
