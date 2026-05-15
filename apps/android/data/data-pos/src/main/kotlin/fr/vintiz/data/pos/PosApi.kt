package fr.vintiz.data.pos

import fr.vintiz.data.pos.dto.CreateTransactionRequest
import fr.vintiz.data.pos.dto.DrawerCloseRequest
import fr.vintiz.data.pos.dto.DrawerOpenRequest
import fr.vintiz.data.pos.dto.DrawerResponse
import fr.vintiz.data.pos.dto.TransactionResponse
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface PosApi {

    @POST("api/v1/pos/transactions")
    suspend fun createTransaction(@Body body: CreateTransactionRequest): TransactionResponse

    @POST("api/v1/pos/transactions/{id}/refund")
    suspend fun refund(@Path("id") id: String): TransactionResponse

    @Streaming
    @GET("api/v1/pos/transactions/{id}/escpos")
    suspend fun receiptEscPosBytes(
        @Path("id") id: String,
        @Query("kick_drawer") kickDrawer: Boolean = false,
    ): ResponseBody

    @POST("api/v1/pos/drawer/open")
    suspend fun drawerOpen(@Body body: DrawerOpenRequest): DrawerResponse

    @POST("api/v1/pos/drawer/close")
    suspend fun drawerClose(@Body body: DrawerCloseRequest): DrawerResponse

    @GET("api/v1/pos/drawer/current")
    suspend fun drawerCurrent(): DrawerResponse?
}
