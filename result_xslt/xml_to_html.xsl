<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes"/>
    <xsl:template match="/">
        <html>
            <body>
                <link rel="stylesheet" type="text/css" href="http://www.lnst-project.org/files/result_xslt/xml_to_html.css"/>
                <script type="text/javascript" src="http://www.lnst-project.org/files/result_xslt/xml_to_html.js"/>
                <h2>LNST results</h2>
                <xsl:apply-templates select="results/recipe"/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="recipe">
        <h3><xsl:value-of select="@name"/></h3>
        <table class="lnst_results">
            <tr><th colspan="4">Task</th></tr>
            <tr><th>Host</th><th>Command</th><th>Result</th><th>Result message</th></tr>
            <xsl:apply-templates select="task"/>
        </table>
    </xsl:template>

    <xsl:template match="task">
        <tr><th colspan="4">Task <xsl:value-of select="position()"/></th></tr>
        <xsl:apply-templates select="command">
            <xsl:with-param name="task_id" select="position()"/>
        </xsl:apply-templates>
    </xsl:template>

    <xsl:template match="command[@type='exec']">
        <xsl:param name="task_id"/>
        <tr>
            <xsl:choose>
                <xsl:when test="@bg_id">
                    <xsl:attribute name="onclick">
                        toggleResultData(event, <xsl:value-of select="$task_id"/>, <xsl:value-of select="@bg_id"/>);
                    </xsl:attribute>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:attribute name="onclick">
                        toggleResultData(event);
                    </xsl:attribute>
                </xsl:otherwise>
            </xsl:choose>
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                <xsl:value-of select="@command"/>
                <xsl:if test="@bg_id">
                    bg_id=<xsl:value-of select="@bg_id"/>
                </xsl:if>
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='ctl_wait']">
        <xsl:param name="task_id"/>
        <tr onclick="toggleResultData(event);">
            <td>
                Controller
            </td>
            <td>
                wait <xsl:value-of select="@seconds"/>s
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='test']">
        <xsl:param name="task_id"/>
        <tr>
            <xsl:choose>
                <xsl:when test="@bg_id">
                    <xsl:attribute name="onclick">
                        toggleResultData(event, <xsl:value-of select="$task_id"/>, <xsl:value-of select="@bg_id"/>);
                    </xsl:attribute>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:attribute name="onclick">
                        toggleResultData(event);
                    </xsl:attribute>
                </xsl:otherwise>
            </xsl:choose>
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                <xsl:value-of select="@module"/>
                <xsl:if test="@bg_id">
                    bg_id=<xsl:value-of select="@bg_id"/>
                </xsl:if>
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='config']">
        <xsl:param name="task_id"/>
        <tr onclick="toggleResultData(event);">
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                config
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='intr']">
        <xsl:param name="task_id"/>
        <tr onclick="toggleResultData(event);">
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                interrupt bg_id=<xsl:value-of select="@proc_id"/>
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <xsl:attribute name="id">task_id=<xsl:value-of select="$task_id"/>bg_id=<xsl:value-of select="@proc_id"/></xsl:attribute>
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='kill']">
        <xsl:param name="task_id"/>
        <tr onclick="toggleResultData(event);">
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                kill bg_id=<xsl:value-of select="@proc_id"/>
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <xsl:attribute name="id">task_id=<xsl:value-of select="$task_id"/>bg_id=<xsl:value-of select="@proc_id"/></xsl:attribute>
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
    </xsl:template>

    <xsl:template match="command[@type='wait']">
        <xsl:param name="task_id"/>
        <tr onclick="toggleResultData(event);">
            <td>
                <xsl:value-of select="@host"/>
            </td>
            <td>
                wait for bg_id=<xsl:value-of select="@proc_id"/>
            </td>
            <xsl:apply-templates select="result"/>
        </tr>
        <tr style="display:none;">
            <xsl:attribute name="id">task_id=<xsl:value-of select="$task_id"/>bg_id=<xsl:value-of select="@proc_id"/></xsl:attribute>
            <td></td>
            <td colspan="3">
                <xsl:choose>
                    <xsl:when test="result_data">
                        <xsl:apply-templates select="result_data"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <div class="result_data">
                            This command didn't provide any additional result data.
                        </div>
                    </xsl:otherwise>
                </xsl:choose>
            </td>
        </tr>
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
            <th>Result Data:</th>
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
</xsl:stylesheet>
